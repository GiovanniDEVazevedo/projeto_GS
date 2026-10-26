"""Inicialização da aplicação: configuração, migrações, servidor e worker."""
import argparse
import os
import sys

from . import bootstrap


class ConfiguracaoInvalida(ValueError):
    pass


def _validar_configuracao():
    # Importação tardia: o bootstrap precisa funcionar antes de instalar pacotes.
    from .config import booleano_env
    try:
        porta = int(os.getenv("PORT", "5000"))
    except ValueError:
        raise RuntimeError("PORT deve ser um número entre 1 e 65535.") from None
    if not 1 <= porta <= 65535:
        raise RuntimeError("PORT deve ser um número entre 1 e 65535.")
    booleano_env("START_WORKER", True)
    if booleano_env("ENABLE_NDVI", True):
        from .credenciais_gee import carregar_dados_gee, gee_configurado
        if gee_configurado():
            dados = carregar_dados_gee()
            projeto = os.getenv("GEE_PROJECT", "").strip() or dados.get("project_id")
            if not isinstance(projeto, str) or not projeto.strip():
                raise RuntimeError("O JSON precisa conter project_id ou GEE_PROJECT deve ser preenchido.")
            print("JSON do Earth Engine carregado. O acesso real será verificado na consulta ao satélite.", flush=True)
        else:
            print("Earth Engine sem credencial: a aplicação funcionará com clima, sem NDVI. Cole o JSON no .env e reinicie.", flush=True)
        try:
            cobertura = float(os.getenv("MIN_NDVI_COVERAGE", "0.5"))
        except ValueError:
            raise RuntimeError("MIN_NDVI_COVERAGE deve estar entre 0 e 1.") from None
        if not 0 <= cobertura <= 1:
            raise RuntimeError("MIN_NDVI_COVERAGE deve estar entre 0 e 1.")


def validar_configuracao():
    try:
        _validar_configuracao()
    except (ValueError, RuntimeError) as erro:
        # Apenas mensagens das validações controladas podem aparecer no console.
        raise ConfiguracaoInvalida(str(erro)) from None


def preparar_aplicacao():
    from dotenv import load_dotenv
    caminho_env = bootstrap.preparar_env()
    load_dotenv(caminho_env, override=False)
    validar_configuracao()
    from .db import migrar
    print("Preparando banco e aplicando migrações...", flush=True)
    migrar()
    print("Banco pronto.", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Inicia o SafraSmart no ambiente já instalado.")
    parser.add_argument("--preparar", action="store_true", help="Valida configuração e aplica migrações sem abrir o servidor")
    args = parser.parse_args(argv)
    try:
        preparar_aplicacao()
        if not args.preparar:
            from .api.server import iniciar_servidor
            iniciar_servidor()
        return 0
    except ConfiguracaoInvalida as erro:
        print(f"Configuração inválida: {erro}", file=sys.stderr)
        return 1
    except ImportError:
        print("Dependências ausentes. Execute python iniciar.py para preparar o ambiente.", file=sys.stderr)
        return 1
    except OSError as erro:
        print(f"Falha ao iniciar ({type(erro).__name__}). Confira a pasta do projeto e a porta configurada.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    except Exception as erro:
        # Erros de banco podem conter URL, SQL e parâmetros: não imprimir segredos.
        print(f"Falha na inicialização ({type(erro).__name__}). Confira a conexão do banco e as migrações.", file=sys.stderr)
        return 1
