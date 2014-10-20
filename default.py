#! /usr/bin/python
# vim:ts=4:sw=4:ai:et:si:sts=4:fileencoding=utf-8

# http://wiki.xbmc.org/index.php?title=How-to:Debug_Python_Scripts_with_Eclipse

REMOTE_DBG = False

# append pydev remote debugger
if REMOTE_DBG:
	# Make pydev debugger works for auto reload.
	# Note pydevd module need to be copied in XBMC\system\python\Lib\pysrc
	try:
		import pysrc.pydevd as pydevd
	# stdoutToServer and stderrToServer redirect stdout and stderr to eclipse console
		pydevd.settrace('localhost', stdoutToServer=True, stderrToServer=True)
		#pydevd.settrace('localhost', port=5678, stdoutToServer=True, stderrToServer=True)
		
	except ImportError:
		sys.stderr.write("Error: " +
			"You must add org.python.pydev.debug.pysrc to your PYTHONPATH.")
		sys.exit(1)


import os
import sys
import inspect
import re
import cookielib
import urllib2
import logging

from loggingexception import LoggingException
from BeautifulSoup import BeautifulSoup
from ConfigParser import SafeConfigParser

logger = logging.getLogger(__name__)

scriptdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))

persistDir = '/opt/prf/persist/irishtv'
configFile = persistDir + '/config/irishtv.conf'
config = SafeConfigParser()
try:
    config.readfp(open(configFile))
except Exception, e:
    logger.error("Error: %s" % e)

import mycgi

from httpmanager import HttpManager

dbg = (config.get("general", "debug") == "true")
dbglevel = 3

from socket import setdefaulttimeout
from socket import getdefaulttimeout

import utils
import rtmp

import providerfactory
from provider import Provider

xhausUrl = "http://www.xhaus.com/headers"

# Use masterprofile rather profile, because we are caching data that may be used by more than one user on the machine
CACHE_FOLDER = persistDir + "/cache"
RESOURCE_PATH = os.path.join( scriptdir, u"resources" )
MEDIA_PATH = os.path.join( RESOURCE_PATH, u"media" )
PROFILE_DATA_FOLDER = persistDir + "/profile"
COOKIE_PATH = os.path.join( PROFILE_DATA_FOLDER, u"cookiejar.txt" )


logger.info("Loading cookies from :" + repr(COOKIE_PATH))
cookiejar = cookielib.LWPCookieJar(COOKIE_PATH)

if os.path.exists(COOKIE_PATH):
    try:
        cookiejar.load()
    except:
        pass

cookie_handler = urllib2.HTTPCookieProcessor(cookiejar)
opener = urllib2.build_opener(cookie_handler)

httpManager = HttpManager()


def get_system_platform():
	platform = "linux"
	logger.debug(u"Platform: %s" % platform)
	return platform

__platform__	 = get_system_platform()


def ShowProviders():
	listItems = []
	contextMenuItems = []
	contextMenuItems.append(('Clear HTTP Cache', "XBMC.RunPlugin(%s?clearcache=1)" % sys.argv[0] ))
	contextMenuItems.append(('Test Forwarded IP', "XBMC.RunPlugin(%s?testforwardedip=1)" % sys.argv[0] ))
	
	providers = providerfactory.getProviderList()


	for provider in providers:
		if not provider.ShowMe():
			continue
		
		provider.SetResourceFolder(RESOURCE_PATH)
		providerName = provider.GetProviderId()
		logger.debug(u"Adding " + providerName + u" provider")
        newListItem = { 'label' : providerName }
		url = u'provider: ' + providerName

		logger.debug(u"url: " + url)
		thumbnailPath = provider.GetThumbnailPath(providerName)
		logger.debug(providerName + u" thumbnail: " + thumbnailPath)
        newListItem.update({'thumbnail' : thumbnailPath,
                            'contextMenuItems' : contextMenuItems })
		listItems.append( (url,newListItem,True) )
	
    return listItems
		

#==============================================================================

def InitTimeout():
	logger.debug(u"getdefaulttimeout(): " + str(getdefaulttimeout()))
	environment = os.environ.get( u"OS", u"linux" )
	if environment in [u'Linux', u'xbox']:
		try:
			timeout = int(config.get("general", 'socket-timeout', "60"))
			if (timeout > 0):
				setdefaulttimeout(timeout)
		except:
			setdefaulttimeout(None)

def TestForwardedIP(forwardedIP):
	try:
		html = None
		logger.info(u"TestForwardedIP: " + forwardedIP)
		httpManager.EnableForwardedForIP()
		httpManager.SetForwardedForIP( forwardedIP )
		html = httpManager.GetWebPageDirect( xhausUrl )
		
		soup = BeautifulSoup(html)
		xForwardedForString = soup.find(text='X-Forwarded-For')
		
		if xForwardedForString is None:
			logger.error("Test failed: X-Forwarded-For header not received by website")
		else:
			forwardedForIP = xForwardedForString.parent.findNextSibling('td').text
			logger.info("Test passed: X-Forwarded-For header received as %s" % forwardedForIP)
			
		return True
		
	except (Exception) as exception:
		if not isinstance(exception, LoggingException):
			exception = LoggingException.fromException(exception)

        logger.warning("Test inconclusive: Error processing web page")
		
		# Error getting web page
		exception.addLogMessage("Error getting web page")
		exception.printLogMessages(logging.ERROR)
		return False


	
#==============================================================================
def executeCommand():
	success = False

	if ( mycgi.EmptyQS() ):
		success = ShowProviders()
	else:
		(providerName, clearCache, testForwardedIP) = mycgi.Params( u'provider', u'clearcache', u'testforwardedip' )

		if clearCache != u'':
			httpManager.ClearCache()
			return True
		
		elif testForwardedIP != u'':
			provider = Provider()

			httpManager.SetDefaultHeaders( provider.GetHeaders() )
			forwardedIP = provider.CreateForwardedForIP('0.0.0.0')
			
			return TestForwardedIP(forwardedIP)
			
		elif providerName != u'':
			logger.debug(u"providerName: " + providerName)
			if providerName <> u'':
				provider = providerfactory.getProvider(providerName)
				
				if provider is None:
					# ProviderFactory return none for providerName: %s
					logException = LoggingException("ProviderFactory returned None for providerName: %s" % providerName)
					# 'Cannot proceed', Error processing provider name
					logException.process("Cannot proceed", "Error processing provider name", logging.ERROR)
					return False
				
				if provider.initialise(httpManager, PROFILE_DATA_FOLDER, RESOURCE_PATH, config):
					success = provider.ExecuteCommand(mycgi)
					logger.debug(u"executeCommand done")

				"""
				print cookiejar
				print 'These are the cookies we have received so far :'

				for index, cookie in enumerate(cookiejar):
					print index, '  :  ', cookie
				cookiejar.save() 
				"""

	return success
#		if ( search <> '' ):
#			error = DoSearch()
#		elif ( showId <> '' and episodeId == ''):
#			error = ShowEpisodes( showId, title )
#		elif ( category <> '' ):
#			error = ShowCategory( category, title, order, page )
#		elif ( episodeId <> '' ):
#			(episodeNumber, seriesNumber, swfPlayer) = mycgi.Params( 'episodeNumber', 'seriesNumber', 'swfPlayer' )
#			error = PlayOrDownloadEpisode( showId, int(seriesNumber), int(episodeNumber), episodeId, title, swfPlayer )
#	


if __name__ == u"__main__":

		try:
			if config.get("general", 'http-cache-disable', 'False') == 'False':
				httpManager.SetCacheDir( CACHE_FOLDER )
	
			InitTimeout()
		
			# Each command processes a web page
			# Get the web page from the cache if it's there
			# If there is an error when processing the web page from the cache
			# we want to try again, this time getting the page from the web
			httpManager.setGetFromCache(True)
			success = executeCommand()			
	
			logger.debug(u"success: %s, getGotFromCache(): %s" % (unicode(success), unicode(httpManager.getGotFromCache())))
			
			if success is not None and success == False and httpManager.getGotFromCache() == True:
				httpManager.setGetFromCache(False)
				executeCommand()
				logger.debug(u"executeCommand after")
				
		except:
			# Make sure the text from any script errors are logged
			import traceback
			traceback.print_exc(file=sys.stdout)
			raise

