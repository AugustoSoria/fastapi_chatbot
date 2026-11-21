"""Tests de la resolución de IP del cliente (anti-spoofing de X-Forwarded-For)."""

from types import SimpleNamespace

import pytest

from app.rate_limit import client_ip


def _req(xff=None, socket_ip="10.0.0.1"):
    """Request falso mínimo: solo headers y client.host, que es lo que usa client_ip."""
    headers = {}
    if xff is not None:
        headers["x-forwarded-for"] = xff
    return SimpleNamespace(headers=headers, client=SimpleNamespace(host=socket_ip))


def test_sin_xff_usa_ip_del_socket():
    assert client_ip(_req(xff=None, socket_ip="10.0.0.1")) == "10.0.0.1"


def test_con_un_proxy_toma_la_ip_real_no_la_del_proxy():
    # Render agrega la IP real al final: "<real>". Un solo salto -> la última.
    assert client_ip(_req(xff="203.0.113.7")) == "203.0.113.7"


def test_cliente_que_falsea_xff_no_evade_el_limite():
    # El atacante manda "XFF: 1.2.3.4" y el proxy de Render agrega su IP real.
    # Tomar la derecha (la que agregó el proxy) ignora el valor falseado.
    assert client_ip(_req(xff="1.2.3.4, 203.0.113.7")) == "203.0.113.7"


def test_espacios_entre_ips():
    assert client_ip(_req(xff="  1.2.3.4 ,  203.0.113.7  ")) == "203.0.113.7"


def test_xff_vacio_cae_al_socket():
    assert client_ip(_req(xff="   ", socket_ip="10.0.0.9")) == "10.0.0.9"


def test_dos_saltos_configurables(monkeypatch):
    # Con un proxy extra (ej. Cloudflare delante de Render): "<real>, <render>".
    # Con TRUSTED_PROXY_HOPS=2 hay que tomar el anteúltimo.
    import app.rate_limit as rl

    monkeypatch.setattr(rl, "TRUSTED_PROXY_HOPS", 2)
    assert rl.client_ip(_req(xff="1.2.3.4, 203.0.113.7, 172.16.0.1")) == "203.0.113.7"
