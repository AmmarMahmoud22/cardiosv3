import logging
import socket
from contextlib import contextmanager

from zeroconf import ServiceInfo, Zeroconf


logger = logging.getLogger(__name__)
SERVICE_TYPE = '_cardios._tcp.local.'
SERVICE_NAME = f'Cardios ECG API.{SERVICE_TYPE}'


def local_ipv4_address():
    route_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        route_socket.connect(('8.8.8.8', 80))
        return route_socket.getsockname()[0]
    finally:
        route_socket.close()


@contextmanager
def advertise_cardios_api(port):
    try:
        address = local_ipv4_address()
    except OSError as error:
        logger.warning('Cardios API discovery is unavailable: %s', error)
        yield
        return

    service = ServiceInfo(
        SERVICE_TYPE,
        SERVICE_NAME,
        addresses=[socket.inet_aton(address)],
        port=port,
        properties={'path': '/device-ecg'},
        server='cardios.local.',
    )
    zeroconf = Zeroconf()
    zeroconf.register_service(service, allow_name_change=True)
    logger.info('Cardios API discovery is available at %s:%s', address, port)

    try:
        yield
    finally:
        zeroconf.unregister_service(service)
        zeroconf.close()
