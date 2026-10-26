"""Preparação local somente com a biblioteca padrão do Python."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parent.parent


def preparar_env():
    destino = ROOT / ".env"
    if destino.exists():
        return destino
    conteudo = (ROOT / ".env.example").read_text(encoding="utf-8")
    try:
        with destino.open("x", encoding="utf-8") as arquivo:
            arquivo.write(conteudo)
        print(".env criado. Cole o JSON do Earth Engine em GEE_SERVICE_ACCOUNT_JSON para ativar o satélite.", flush=True)
    except FileExistsError:
        pass  # Nunca substituir configurações ou credenciais já existentes.
    return destino


def assinatura_dependencias():
    assinatura = hashlib.sha256(f"bootstrap-v1:{sys.version_info[:2]}".encode())
    for nome in ("requirements.txt", "requirements-ndvi.txt"):
        assinatura.update(nome.encode())
        assinatura.update((ROOT / nome).read_bytes())
    return assinatura.hexdigest()


def preparar_ambiente():
    ambiente = ROOT / ".venv"
    python = ambiente / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.is_file():
        print("Criando ambiente virtual .venv...", flush=True)
        venv.EnvBuilder(with_pip=True).create(ambiente)
    assinatura = assinatura_dependencias()
    marcador = ambiente / ".safrasmart-dependencias"
    atualizado = marcador.is_file() and marcador.read_text(encoding="utf-8") == assinatura
    if atualizado:
        # Também detectar um ambiente incompleto após remoção manual de pacotes.
        teste = subprocess.run([str(python), "-c", "import flask, requests, sqlalchemy, alembic, dotenv, ee"],
                               cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        atualizado = teste.returncode == 0
    if not atualizado:
        print("Instalando dependências, incluindo Earth Engine...", flush=True)
        subprocess.run([str(python), "-m", "pip", "install", "--disable-pip-version-check", "--quiet", "-r", str(ROOT / "requirements-ndvi.txt")],
                       cwd=ROOT, check=True)
        marcador.write_text(assinatura, encoding="utf-8")
    return python


def main(argv=None):
    parser = argparse.ArgumentParser(description="Prepara e inicia o SafraSmart com um comando.")
    parser.add_argument("--preparar", action="store_true", help="Prepara ambiente, configuração e banco sem abrir o servidor")
    args = parser.parse_args(argv)
    if sys.version_info < (3, 10):
        print("É necessário Python 3.10 ou superior.", file=sys.stderr)
        return 1
    try:
        preparar_env()
        python = preparar_ambiente()
        comando = [str(python), "-m", "safrasmart"]
        if args.preparar:
            comando.append("--preparar")
        ambiente = os.environ.copy()
        ambiente["VIRTUAL_ENV"] = str(ROOT / ".venv")
        ambiente["PATH"] = str(python.parent) + os.pathsep + ambiente.get("PATH", "")
        ambiente.setdefault("PYTHONUTF8", "1")
        return subprocess.run(comando, cwd=ROOT, env=ambiente).returncode
    except subprocess.CalledProcessError:
        print("Não foi possível instalar as dependências. Confira o erro de instalação acima e tente novamente.", file=sys.stderr)
        return 1
    except OSError as erro:
        print(f"Não foi possível preparar o ambiente ({type(erro).__name__}). Confira as permissões da pasta e a instalação do Python.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
