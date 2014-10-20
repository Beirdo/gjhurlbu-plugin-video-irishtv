#! /usr/bin/python
# vim:ts=4:sw=4:ai:et:si:sts=4:fileencoding=utf-8
#import xbmc
#from xbmc import log
#from xbmcaddon import Addon
from loggingexception import LoggingException

from rte import RTEProvider
from tv3 import TV3Provider
#from aertv import AerTVProvider
from tg4 import TG4Provider
import logging

logger = logging.getLogger(__name__)

# Provider names

#__providers__ = [RTEProvider(), TV3Provider(), AerTVProvider(), TG4Provider()]
__providers__ = [RTEProvider(), TV3Provider(), TG4Provider()]


def getProvider(name):
    logger.debug("ProviderFactory(" + str(name) + ")")

    for provider in __providers__:
        if name == provider.GetProviderId():
            return provider

    return None

def getProviderList():
    return __providers__
