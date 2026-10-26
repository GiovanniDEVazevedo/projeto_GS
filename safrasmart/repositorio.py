"""Transações curtas; nenhum serviço externo é chamado dentro delas."""
import hashlib
import json
from datetime import date, timedelta
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError

from .db import Analise, CacheDado, Propriedade, Safra, agora, sessoes


class Conflito(ValueError):
    pass


def identificador(*partes):
    return str(uuid5(NAMESPACE_URL, json.dumps(partes, ensure_ascii=False)))


def serializar(item):
    return {
        "id": item.operacao_id, "status": item.status,
        "persistido": True, "resultado": item.resultado, "erro": item.erro,
        "tentativas": item.tentativas, "safra_id": item.safra_id,
        "criado_em": item.criado_em.isoformat() + "Z",
        "atualizado_em": item.atualizado_em.isoformat() + "Z",
        "versao_motor": item.versao_motor,
    }


class Repositorio:
    def __init__(self, engine):
        self.engine = engine
        self.session = sessoes(engine)

    def registrar(self, dono, dados):
        assinatura = hashlib.sha256(json.dumps(dados, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        aid = identificador("analise", dono, dados["id"])
        pid = identificador("propriedade", dono, dados["propriedade"], dados["lat"], dados["lon"])
        sid = identificador("safra", pid, dados["cultura"], dados["data_plantio"], dados["solo"], dados["irrigacao"])
        # Repetir a transação resolve tanto colisões da operação quanto a criação
        # concorrente da mesma propriedade/safra em operações diferentes.
        for tentativa in range(3):
            try:
                with self.session.begin() as s:
                    existente = s.get(Analise, aid)
                    if existente:
                        if existente.assinatura != assinatura:
                            raise Conflito("Este id já foi usado com outros dados. Crie uma nova operação.")
                        return serializar(existente)
                    if not s.get(Propriedade, pid):
                        s.add(Propriedade(id=pid, dono=dono, nome=dados["propriedade"],
                            lat=dados["lat"], lon=dados["lon"], precisao_m=dados["precisao_m"],
                            origem_localizacao=dados["origem_localizacao"]))
                        s.flush()
                    if not s.get(Safra, sid):
                        s.add(Safra(id=sid, propriedade_id=pid, cultura=dados["cultura"],
                            data_plantio=date.fromisoformat(dados["data_plantio"]),
                            solo=dados["solo"], irrigacao=dados["irrigacao"]))
                        s.flush()
                    item = Analise(id=aid, operacao_id=dados["id"], dono=dono, safra_id=sid,
                                   assinatura=assinatura, entrada=dados)
                    s.add(item)
                    s.flush()
                    resposta = serializar(item)
                # Retorno somente DEPOIS do commit: confirmação significa durabilidade.
                return resposta
            except IntegrityError:
                if tentativa == 2:
                    raise

    def obter(self, dono, operacao_id):
        with self.session() as s:
            item = s.scalar(select(Analise).where(Analise.dono == dono, Analise.operacao_id == operacao_id))
            return serializar(item) if item else None

    def listar(self, dono, limite=50, pagina=1):
        with self.session() as s:
            itens = s.scalars(select(Analise).where(Analise.dono == dono)
                .order_by(Analise.criado_em.desc(), Analise.id).offset((pagina - 1) * limite).limit(limite))
            return [serializar(item) for item in itens]

    def propriedades(self, dono):
        with self.session() as s:
            return [{"id": p.id, "nome": p.nome, "lat": p.lat, "lon": p.lon}
                    for p in s.scalars(select(Propriedade).where(Propriedade.dono == dono).limit(200))]

    def safras(self, dono):
        with self.session() as s:
            return [{"id": sf.id, "propriedade_id": sf.propriedade_id, "cultura": sf.cultura,
                     "data_plantio": sf.data_plantio.isoformat(), "solo": sf.solo, "irrigacao": sf.irrigacao}
                    for sf in s.scalars(select(Safra).join(Propriedade).where(Propriedade.dono == dono).limit(200))]

    def reivindicar(self, lease_segundos=300):
        momento = agora()
        elegivel = or_(and_(Analise.status == "pendente", Analise.disponivel_em <= momento),
                       and_(Analise.status == "processando", Analise.lease_ate < momento))
        with self.session.begin() as s:
            # Um processo morto também consome uma tentativa. Sem este limite,
            # quedas repetidas deixariam o mesmo trabalho em execução para sempre.
            s.execute(update(Analise).where(
                Analise.status == "processando", Analise.lease_ate < momento,
                Analise.tentativas >= 3).values(
                    status="erro", lease_token=None, lease_ate=None,
                    atualizado_em=momento,
                    erro="Processamento interrompido após 3 tentativas. Os dados foram preservados."))
            # UPDATE condicional funciona também no SQLite. Dois workers podem
            # selecionar o mesmo id; somente um consegue adquirir a lease.
            ids = s.scalars(select(Analise.id).where(elegivel).order_by(Analise.criado_em).limit(10)).all()
            for aid in ids:
                token = str(uuid4())
                r = s.execute(update(Analise).where(Analise.id == aid, elegivel).values(
                    status="processando", lease_token=token, lease_ate=momento + timedelta(seconds=lease_segundos),
                    tentativas=Analise.tentativas + 1, atualizado_em=momento))
                if r.rowcount == 1:
                    item = s.get(Analise, aid)
                    return {"id": item.id, "token": token, "entrada": item.entrada, "tentativas": item.tentativas}
        return None

    def finalizar(self, job, resultado=None, erro=None):
        valores = {"lease_token": None, "lease_ate": None, "atualizado_em": agora(), "erro": erro}
        if erro:
            valores.update(status="pendente" if job["tentativas"] < 3 else "erro",
                           disponivel_em=agora() + timedelta(seconds=30 * 2 ** min(job["tentativas"], 5)))
        else:
            valores.update(status="ok", resultado=resultado)
        with self.session.begin() as s:
            r = s.execute(update(Analise).where(Analise.id == job["id"], Analise.lease_token == job["token"])
                          .values(**valores))
            return r.rowcount == 1  # um worker atrasado não sobrescreve outro

    def devolver(self, job):
        """Parada normal: devolver a operação sem consumir uma tentativa."""
        with self.session.begin() as s:
            r = s.execute(update(Analise).where(Analise.id == job["id"], Analise.lease_token == job["token"])
                .values(status="pendente", lease_token=None, lease_ate=None, erro=None,
                        tentativas=Analise.tentativas - 1, disponivel_em=agora(), atualizado_em=agora()))
            return r.rowcount == 1

    def status_worker(self):
        # Usa o cache existente: não exige uma nova tabela ou migração.
        with self.session() as s:
            ativos = s.scalar(select(func.count()).select_from(CacheDado).where(
                CacheDado.chave.like("worker:%"), CacheDado.expira_em > agora()))
        return {"ativo": ativos > 0, "instancias": ativos}

    def cache_remover(self, chave):
        with self.session.begin() as s:
            s.execute(delete(CacheDado).where(CacheDado.chave == chave))

    def cache_get(self, chave):
        with self.session() as s:
            item = s.get(CacheDado, chave)
            return item.conteudo if item and item.expira_em > agora() else None

    def cache_set(self, chave, conteudo, ttl):
        for tentativa in range(2):
            try:
                with self.session.begin() as s:
                    s.merge(CacheDado(chave=chave, conteudo=conteudo, expira_em=agora() + timedelta(seconds=ttl)))
                return
            except IntegrityError:
                if tentativa:
                    raise
