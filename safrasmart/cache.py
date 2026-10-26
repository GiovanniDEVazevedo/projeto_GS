import hashlib
import json


class CacheAnalitico:
    def __init__(self, repositorio):
        self.repo = repositorio

    def obter_ou_calcular(self, parametros, calcular, ttl=21600, cachear=None):
        chave = hashlib.sha256(json.dumps(parametros, sort_keys=True).encode()).hexdigest()
        existente = self.repo.cache_get(chave)
        if existente is not None and (cachear is None or cachear(existente)):
            return existente
        resultado = calcular()
        # Falhas externas não ficam armazenadas como dados válidos.
        if resultado and (cachear is None or cachear(resultado)):
            self.repo.cache_set(chave, resultado, ttl)
        return resultado
