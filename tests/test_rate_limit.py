"""Tests de la resolución de IP del cliente a partir de X-Forwarded-For."""

from types import SimpleNamespace

import pytest

import app.rate_limit as rl
from app.rate_limit import client_ip

IP1 = "198.51.100.10"
IP2 = "203.0.113.20"
IP3 = "192.0.2.30"


def _req(xff=None, socket_ip="10.0.0.1"):
    headers = {}
    if xff is not None:
        headers["x-forwarded-for"] = xff
    return SimpleNamespace(headers=headers, client=SimpleNamespace(host=socket_ip))


@pytest.fixture
def hops(monkeypatch):
    def _set(n):
        monkeypatch.setattr(rl, "TRUSTED_PROXY_HOPS", n)

    return _set


def test_sin_xff_usa_ip_del_socket():
    assert client_ip(_req(xff=None, socket_ip="10.0.0.1")) == "10.0.0.1"


def test_saltea_las_partes_finales(hops):
    hops(2)
    assert client_ip(_req(xff=f"{IP1}, {IP2}, {IP3}")) == IP1


def test_valores_finales_que_rotan_no_cambian_el_resultado(hops):
    hops(2)
    a = client_ip(_req(xff=f"{IP1}, 203.0.113.44, 192.0.2.77"))
    b = client_ip(_req(xff=f"{IP1}, 203.0.113.102, 192.0.2.14"))
    assert a == b == IP1


def test_prefijo_falseado_no_cambia_el_resultado(hops):
    hops(2)
    assert client_ip(_req(xff=f"1.2.3.4, {IP1}, {IP2}, {IP3}")) == IP1


def test_varios_prefijos_falseados_no_cambian_el_resultado(hops):
    hops(2)
    assert client_ip(_req(xff=f"9.9.9.9, 8.8.8.8, {IP1}, {IP2}, {IP3}")) == IP1


def test_espacios_entre_valores(hops):
    hops(2)
    assert client_ip(_req(xff=f"  {IP1} , {IP2} ,  {IP3}  ")) == IP1


def test_menos_partes_que_saltos_no_revienta(hops):
    hops(2)
    assert client_ip(_req(xff=IP1)) == IP1


def test_xff_vacio_cae_al_socket():
    assert client_ip(_req(xff="   ", socket_ip="10.0.0.9")) == "10.0.0.9"


def test_un_salto(hops):
    hops(1)
    assert client_ip(_req(xff=f"{IP1}, {IP3}")) == IP1
