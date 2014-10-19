#! /usr/bin/python
# vim:ts=4:sw=4:ai:et:si:sts=4:fileencoding=utf-8
import re
import sys
from time import strftime,strptime
import time, random
import urllib
import pyamf
from pyamf.remoting.client import RemotingService
from pyamf import remoting

from datetime import timedelta
from datetime import date
from datetime import datetime
from urlparse import urljoin

import pickle
import base64

#import xbmc

import utils
from loggingexception import LoggingException

import HTMLParser
from BeautifulSoup import BeautifulSoup

from provider import Provider
import logging

logger = logging.getLogger(__name__)

c_brightcove = "http://c.brightcove.com"

class BrightCoveProvider(Provider):

    def __init__(self):
        super(BrightCoveProvider, self).__init__()
        self.amfResponse = None
        self.useBitRateSetting = True

    def ChooseBitRate(self, preferredRate, renditions):
        #if len(renditions) < 2:
        #    return None

        rates = {}
        for rendition in renditions:
            rates[rendition[u'encodingRate']] = rendition
        
        logger.info(u"rates.keys(): %s" % rates.keys())

        #if 0 in rates:
        #    del rates[0]

        if preferredRate is None or preferredRate == -1:
            logger.info(u"min(rates.keys()): %s" % min(rates.keys()))
            return rates[min(rates.keys())][u'defaultURL']

        reverseRates = rates.keys()
        reverseRates.sort()
        reverseRates.reverse()

        logger.info(u"reverseRates: %s" % reverseRates)

        for rate in reverseRates:
            logger.info(u"if bitrate >= %s: %s" %( rate, preferredRate >= rate))
            if preferredRate >= rate:
                return rates[rate][u'defaultURL']

        return rates[min(rates.keys())][u'defaultURL']

    def GetStreamUrl(self, key, url, playerId, contentRefId = None, contentId = None, streamType = "RTMP"):
        logger.debug("")
        try:
            self.amfResponse = None
            self.amfResponse = self.GetEpisodeInfo(key, url, playerId, contentRefId = contentRefId, contentId = contentId)
            name = self.amfResponse[u'name']
           
            logger.info(u"Name field: " + name)
           
            preferredRate = self.GetBitRateSetting()
           
           
            defaultStreamUrl = self.amfResponse[u'programmedContent'][u'videoPlayer'][u'mediaDTO'][u'FLVFullLengthURL']

            logger.info(u"defaultStreamUrl: %s" % defaultStreamUrl)
           
            if preferredRate is None and defaultStreamUrl.upper().startswith(streamType):
                return defaultStreamUrl 

            originalRenditions = self.amfResponse[u'programmedContent'][u'videoPlayer'][u'mediaDTO'][u'renditions']
            logger.info(u"renditions: %s" % utils.drepr(originalRenditions))

            renditions = []
            renditionsOther = []
            for rendition in originalRenditions:
                if rendition[u'encodingRate'] == 0:
                    continue
                
                if rendition['defaultURL'].upper().startswith(streamType):
                    renditions.append(rendition)
                else:
                    renditionsOther.append(rendition)
            
            if len(renditions) == 0:
                logger.warning(u"Unable to find stream of type '%s'" % streamType)
                renditions = renditionsOther

            logger.info(u"renditions: %s" % utils.drepr(renditions))
            bitrate = self.ChooseBitRate(preferredRate, renditions)

            if bitrate == None:
                return defaultStreamUrl
            
            return bitrate

        except (Exception) as exception:
            if not isinstance(exception, LoggingException):
                exception = LoggingException.fromException(exception)

            if self.amfResponse is not None:
                msg = "self.amfResponse:\n\n%s\n\n" % utils.drepr(self.amfResponse)
                exception.addLogMessage(msg)

            raise exception
                
    def GetEpisodeInfo(self, key, url, playerId, contentRefId = None, contentId = None):
        logger.debug(u"RemotingService")
        
        try:            
            if self.proxyConfig is not None: 
                self.proxyConfig.Enable()
            
            serviceName = 'com.brightcove.experience.ExperienceRuntimeFacade'
            service = self.GetRemotingService(key, serviceName)

            hashValue = self.GetAmfClassHash(serviceName)
            logger.info(u'hashValue:' + str(hashValue))
         
            pyamf.register_class(ViewerExperienceRequest, 'com.brightcove.experience.ViewerExperienceRequest')
            pyamf.register_class(ContentOverride, 'com.brightcove.experience.ContentOverride')
            content_override = ContentOverride(contentRefId = contentRefId, contentId = contentId)
            viewer_exp_req = ViewerExperienceRequest(url, [content_override], int(playerId), key)
            
            # Make the request
            response = service.getDataForExperience(hashValue, viewer_exp_req)
            
            logger.debug(u"response: " + utils.drepr(response))
        finally:
            if self.proxyConfig is not None: 
                self.proxyConfig.Disable()
    
        return response

    def FindMediaByReferenceId(self, key, playerId, referenceId, pubId):
        logger.debug("")
        
        try:            
            if self.proxyConfig is not None: 
                self.proxyConfig.Enable()

            serviceName = 'com.brightcove.player.runtime.PlayerMediaFacade'
            service = self.GetRemotingService(key, serviceName)

            hashValue = self.GetAmfClassHash(serviceName)
    
            logger.info(u'hashValue:' + str(hashValue))
     
            response = service.findMediaByReferenceId(hashValue, int(playerId), referenceId, pubId)
            
            logger.debug(u"response: " + utils.drepr(response))

        finally:
            if self.proxyConfig is not None: 
                self.proxyConfig.Disable()
    
        return response

    def GetRemotingService(self, key, serviceName):
        #logger.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)-5.5s [%(name)s] %(message)s')

        headers = self.GetHeaders()
        client = RemotingService(c_brightcove + "/services/messagebroker/amf?playerKey=" + key.encode("ascii"), amf_version=3,logger=logger, user_agent=headers['User-Agent'])

        if self.httpManager.GetIsForwardedForIP():
             forwardedIP = self.httpManager.GetForwardedForIP()
             client.addHeader(u'X-Forwarded-For', forwardedIP)

        # Connect to the Brightcove AMF service
        service = client.getService(serviceName)
  
        return service

    def GetAmfClassHash(self, className):
        return None

    def BuildAmfRequest(self, key, url, exp_id, contentRefId = None, contentId = None):
       logger.info(u'ContentRefId:' + str(contentRefId) + u', ExperienceId:' + str(exp_id) + u', URL:' + url)  

       method = u"com.brightcove.experience.ExperienceRuntimeFacade.getDataForExperience"
       className = method[0:method.rfind('.')]
       hashValue = self.GetAmfClassHash(className)

       logger.info(u'hashValue:' + str(hashValue))
 
       pyamf.register_class(ViewerExperienceRequest, 'com.brightcove.experience.ViewerExperienceRequest')
       pyamf.register_class(ContentOverride, 'com.brightcove.experience.ContentOverride')
       content_override = ContentOverride(contentRefId = contentRefId, contentId = contentId)
       viewer_exp_req = ViewerExperienceRequest(url, [content_override], int(exp_id), key)
    
       logger.info( content_override.tostring() )
       logger.info( viewer_exp_req.tostring() )
    
       env = remoting.Envelope(amfVersion=3)
       env.bodies.append(
          (
             "/1",
             remoting.Request(
                target=method,
                body=[hashValue, viewer_exp_req],
                envelope=env
             )
          )
       )
       return env

    def BuildAmfRequest_FindRelated(self, key, exp_id, pubId, videoPlayer, pageSize, pageNumber, getItemCount):
       logger.info(u'ExperienceId:' + str(exp_id))  

       method = "com.brightcove.player.runtime.PlayerSearchFacade.findRelatedVideos"
       className = method[0:method.rfind('.')]
       hashValue = self.GetAmfClassHash(className)

       logger.info(u'hashValue:' + str(hashValue))
 
       pageSize = 12
       pageNumber = 0
       getItemCount = False

       env = remoting.Envelope(amfVersion=3)
       env.bodies.append(
          (
             "/1",
             remoting.Request(
                target=method,
                body=[hashValue, int(exp_id), pubId, videoPlayer, pageSize, pageNumber, getItemCount],
#                body=[hashValue, "Nuacht", 1, 0, False, None, None, None, None, None],
                envelope=env
             )
          )
       )
       return env

    def GetSwfUrl(self, qsData):
        logger.debug("")
        url = c_brightcove + "/services/viewer/federated_f9?&" + urllib.urlencode(qsData)
        response = self.httpManager.GetHTTPResponse(url)

        location = response.url
        base = location.split(u"?",1)[0]
        location = base.replace(u"BrightcoveBootloader.swf", u"federatedVideoUI/BrightcoveBootloader.swf")
        return location
        

    
class ViewerExperienceRequest(object):
   def __init__(self, URL, contentOverrides, experienceId, playerKey, TTLToken=u''):
      self.TTLToken = TTLToken
      self.URL = URL
      self.deliveryType = float(0)
      self.contentOverrides = contentOverrides
      self.experienceId = experienceId
      self.playerKey = playerKey


   def tostring(self):
      return u"TTLToken: %s, URL: %s, deliveryType: %s, contentOverrides: %s, experienceId: %s, playerKey: %s" % (self.TTLToken, self.URL, self.deliveryType, self.contentOverrides, self.experienceId, self.playerKey)

class ContentOverride(object):
   def __init__(self, contentId = float(0), contentIds = None, contentRefId = None, contentRefIds = None, contentType = 0, featureId = float(0), featuredRefId = None, contentRefIdtarget='videoPlayer'):
      self.contentType = contentType
      self.contentId = contentId
      self.target = contentRefIdtarget
      self.contentIds = contentIds
      self.contentRefId = contentRefId
      self.contentRefIds = contentRefIds
      self.featureId = featureId
      self.featuredRefId = None

   def tostring(self):
      return u"contentType: %s, contentId: %s, target: %s, contentIds: %s, contentRefId: %s, contentRefIds: %s, contentType: %s, featureId: %s, featuredRefId: %s, " % (self.contentType, self.contentId, self.target, self.contentIds, self.contentRefId, self.contentRefIds, self.contentType, self.featureId, self.featuredRefId)
