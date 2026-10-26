import hashlib
import json


class CacheAnalitico:
    def __init__(self, repositorio):
        self.repo = repositorio

    def obter_ou_calcular(self, parametros, calcular, ttl=21600):
        chave = hashlib.sha256(json.dumps(parametros, sort_keys=True).encode()).hexdigest()
        existente = self.repo.cache_get(chave)
        if existente is not None:
            return existente
        resultado = calcular()
        # Falhas externas não ficam armazenadas como dados válidos.
        if resultado:
            self.repo.cache_set(chave, resultado, ttl)
        return resultado
