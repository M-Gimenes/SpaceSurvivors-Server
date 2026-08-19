"""Ponto de entrada WSGI (PythonAnywhere aponta para `application` aqui)."""
from app import create_app

application = create_app()

if __name__ == '__main__':
    application.run()
