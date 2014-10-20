#! /usr/bin/python
# vim:ts=4:sw=4:ai:et:si:sts=4:fileencoding=utf-8

import re
import sys
from time import mktime,strptime,time
from datetime import timedelta
from datetime import date
from datetime import datetime
from urlparse import urljoin


#import xbmc
#import xbmcgui
#import xbmcplugin

import mycgi
import utils
from loggingexception import LoggingException
import rtmp

#from resumeplayer import ResumePlayer
#from watched import WatchedPlayer
from provider import Provider
import HTMLParser

from BeautifulSoup import BeautifulSoup
from BeautifulSoup import BeautifulStoneSoup
import logging

logger = logging.getLogger(__name__)

urlRoot = u"http://www.rte.ie"
rootMenuUrl = u"http://www.rte.ie/player/ie/"
showUrl = u"http://www.rte.ie/player/ie/show/%s/"

flashJS = u"http://static.rasset.ie/static/player/js/flash-player.js"
configUrl = u"http://www.rte.ie/playerxl/config/config.xml"

playerJSDefault = u"http://static.rasset.ie/static/player/js/player.js?v=5"
searchUrlDefault = u"http://www.rte.ie/player/ie/search/?q="
swfDefault = u"http://www.rte.ie/player/assets/player_468.swf"
"""
swfLiveDefault = u"http://www.rte.ie/static/player/swf/osmf2_541_2012_11_14.swf"
swfLiveDefault = u"http://www.rte.ie/player/assets/player_468.swf"
"""
swfLiveDefault = u"http://www.rte.ie/static/player/swf/osmf2_2013_06_25b.swf"
defaultLiveTVPage = u"/player/ie/live/8/"

episodeMap = { 'programme' : 'Title', 'description' : 'Plot',
               'categories' : 'Genre', 'duration' : 'duration',
               'datemodified' : 'pubDate', 'channel' : 'station' }

class RTEProvider(Provider):

#    def __init__(self):
#        self.cache = cache

    def GetProviderId(self):
        return u"RTE"

    def ExecuteCommand(self, mycgi):
        return super(RTEProvider, self).ExecuteCommand(mycgi)

    def ShowRootMenu(self):
        logger.debug(u"")
        
        try:
            html = None
            html = self.httpManager.GetWebPage(rootMenuUrl, 60)
    
            if html is None or html == '':
                # Error getting %s Player "Home" page
                logException = LoggingException("Error getting %s Player Home page" % self.GetProviderId())
                # 'Cannot show RTE root menu', Error getting RTE Player "Home" page
                logException.process("Cannot show RTE root menu", "Error getting %s Player Home page" % self.GetProviderId(), self.logLevel(logging.ERROR))
                return False
    
            soup = BeautifulSoup(html, selfClosingTags=['img'])
            categories = soup.find(u'div', u"dropdown-programmes")
    
            if categories == None:
                # "Can't find dropdown-programmes"
                logException = LoggingException("Can't find dropdown-programmes")
                # 'Cannot show RTE root menu', Error parsing web page
                logException.process("Cannot show RTE root menu", "Error processing web page", self.logLevel(logging.ERROR))
                #raise logException
                return False
            
            listItems = []
    
            try:
                listItems.append( self.CreateSearchItem() )
            except (Exception) as exception:
                if not isinstance(exception, LoggingException):
                    exception = LoggingException.fromException(exception)

                # Not fatal, just means that we don't have the search option
                exception.process(severity = logging.WARNING)
    
            if False == self.AddAllLinks(listItems, categories, autoThumbnails = True):
                return False
            
            newLabel = u"Live"
            thumbnailPath = self.GetThumbnailPath(newLabel)
            newListItem = { 'label' : newLabel, 'thumbnail' : thumbnailPath }
#            newListItem = xbmcgui.ListItem( label=newLabel )
#            newListItem.setThumbnailImage(thumbnailPath)
            url = self.GetURLStart() + u'&live=1'
            listItems.append( (url, newListItem, True) )

#            xbmcplugin.addDirectoryItems( handle=self.pluginHandle, items=listItems )
#            xbmcplugin.endOfDirectory( handle=self.pluginHandle, succeeded=True )
            
#            return True
            return listItems
        except (Exception) as exception:
            if not isinstance(exception, LoggingException):
                exception = LoggingException.fromException(exception)

            if html is not None:
                msg = "html:\n\n%s\n\n" % html
                exception.addLogMessage(msg)
                
            # Cannot show root menu
            exception.addLogMessage("Cannot show root menu")
            exception.process(severity = self.logLevel(logging.ERROR))
            return False

    """
    listshows: If '1' list the shows on the main page, otherwise process the sidebar. The main page links to programmes or specific episodes, the sidebar links to categories or sub-categories
    episodeId: id of the show to be played, or the id of a show where more than one episode is available
    listavailable: If '1' process the specified episode as one of at least one episodes available, i.e. list all episodes available
    search: If '1' perform a search
    page: url, relative to www.rte.ie, to be processed. Not passed when an episodeId is given.
    live: If '1' show live menu
    """
    def ParseCommand(self, mycgi):
        (listshows, episodeId, listAvailable, search, page, live, resume) = mycgi.Params( u'listshows', u'episodeId', u'listavailable', u'search', u'page', u'live', u'resume'  )
        logging.debug(u"")
        logging.debug(u"listshows: %s, episodeId %s, listAvailable %s, search %s, page %s, resume: %s" % (str(listshows), episodeId, str(listAvailable), str(search), page, str(resume)))

       
        if episodeId <> '':
            resumeFlag = False
            if resume <> u'':
                resumeFlag = True
           
            #return self.PlayEpisode(episodeId)
            return self.PlayVideoWithDialog(self.PlayEpisode, (episodeId, resumeFlag))

        if search <> '':
            if page == '':
                return self.DoSearch(search)
            else:
                return self.DoSearchQuery( queryUrl = urlRoot + page)
                 
        if page == '':
            if live <> '':
                return self.ShowLiveMenu()
            
            # "Can't find 'page' parameter "
            logException = LoggingException(logMessage = "Can't find 'page' pareameter")
            # 'Cannot proceed', Error processing command
            logException.process("Cannot show root menu", "Error processing web page", self.logLevel(logging.ERROR))
            return False

        page = page
        # TODO Test this
        logger.debug(u"page = %s" % page)
        #self.log(u"type(page): " + repr(type(page)), xbmc.LOGDEBUG)
        ##page = mycgi.URLUnescape(page)
        #self.log(u"page = %s" % page, xbmc.LOGDEBUG)
        #self.log(u"type(mycgi.URLUnescape(page)): " + repr(type(page)), xbmc.LOGDEBUG)
#        self.log(u"mycgi.URLUnescape(page) = %s" % page, xbmc.LOGDEBUG)

        if u' ' in page:
            page = page.replace(u' ', u'%20')

        try:
            logger.info(u"urlRoot: " + urlRoot + u", page: " + page )
            html = None
            html = self.httpManager.GetWebPage( urlRoot + page, 1800 )
        except (Exception) as exception:
            if not isinstance(exception, LoggingException):
                exception = LoggingException.fromException(exception)

            if html is not None:
                msg = "html:\n\n%s\n\n" % html
                exception.addLogMessage(msg)
                
            # Error getting web page
            exception.addLogMessage("Error getting web page")
            exception.process(severity = self.logLevel(logging.ERROR))
            return False

        if live <> '':
            #return self.PlayLiveTV(html)
            return self.PlayVideoWithDialog(self.PlayLiveTV, (html, None))
            
        if listshows <> u'':
            return self.ListShows(html)
        
        if listAvailable <> u'':
            
            soup = BeautifulSoup(html)
            availableLink = soup.find('a', 'button-more-episodes')
            
            if availableLink is None:
                pattern= "/player/ie/show/(.+)/"
                match=re.search(pattern, html, re.DOTALL)
                
                if match is not None:
                    episodeId = match.group(1) 
                    resumeFlag = False
                    if resume <> u'':
                        resumeFlag = True

                    return self.PlayVideoWithDialog(self.PlayEpisode, (episodeId, resumeFlag))

                
            return self.ListAvailable(html)

        return self.ListSubMenu(html)

    def GetLivePageUrl(self):
        
        try:
            html = None
            html = self.httpManager.GetWebPage(rootMenuUrl, 60)
    
            soup = BeautifulSoup(html, selfClosingTags=['img'])
            page = soup.find('ul', 'sidebar-live-list').find('a')['href']
        except (Exception) as exception:
            if not isinstance(exception, LoggingException):
                exception = LoggingException.fromException(exception)
        
            if html is not None:
                msg = "html:\n\n%s\n\n" % html
                exception.addLogMessage(msg)
                
            exception.addLogMessage("Unable to determine swfPlayer URL.  Using default: %s" % defaultLiveTVPage)
            exception.process('', '', severity = logging.WARNING)

            page = defaultLiveTVPage
            
        return page

    def ShowLiveMenu(self):
        logger.debug(u"")
        listItems = []
        
        try:
            html = None
            page = self.GetLivePageUrl()
            html = self.httpManager.GetWebPage(urlRoot + page, 60)
            soup = BeautifulSoup(html, selfClosingTags=['img'])
    
            schedule = soup.find('div', 'live-schedule-strap clearfix')
            liList = schedule.findAll('li')

            for li in liList:
                logoName = li.find('span', {'class':re.compile('live-logo')})
                channel = logoName.text
                thumbnailPath = self.GetThumbnailPath((channel.replace(u'RT\xc9 ', '')).replace(' ', ''))
                page = li.a['href']

                infoList=li.findAll('span', "live-channel-info")
                programme = ""
                for info in infoList:
                    text = info.text.replace("&nbsp;", "")
                    if len(text) == 0:
                        continue
                    
                    comma = ""
                    if len(programme) == 0:
                        programme = info.text
                    else:
                        programme = programme + ", " + info.text

                programme = programme.replace('&#39;', "'")
                newListItem = { 'label' : programme,
                                'thumbnail' : thumbnailPath, 'Video' : True }
#                newListItem = xbmcgui.ListItem( label=programme )
#                newListItem.setThumbnailImage(thumbnailPath)
#                newListItem.setProperty("Video", "true")
#                #newListItem.setProperty('IsPlayable', 'true')

                url = self.GetURLStart() + u'&live=1' + u'&page=' + mycgi.URLEscape(page)
                listItems.append( (url, newListItem, False) )
        
#            xbmcplugin.addDirectoryItems( handle=self.pluginHandle, items=listItems )
#            xbmcplugin.endOfDirectory( handle=self.pluginHandle, succeeded=True )
#            
#            return True
            return listItems
        except (Exception) as exception:
            if not isinstance(exception, LoggingException):
                exception = LoggingException.fromException(exception)

            if html is not None:
                msg = "html:\n\n%s\n\n" % html
                exception.addLogMessage(msg)
                
            # Error getting Live TV information
            exception.addLogMessage("Error adding links")
            exception.process(severity = self.logLevel(logging.ERROR))
            return False

    def CreateSearchItem(self, pageUrl = None):
        try:
            if pageUrl is None or len(pageUrl) == 0:
                newLabel = u"Search"
                url = self.GetURLStart() + u'&search=1'
            else:
                newLabel = u"More..."
                url = self.GetURLStart() + u'&search=1' + u'&page=' + mycgi.URLEscape(pageUrl)
  
            thumbnailPath = self.GetThumbnailPath(u"Search")
            newListItem = { 'label' : newLabel, 'thumbnail' : thumbnailPath }
#            newListItem = xbmcgui.ListItem( label=newLabel )
#            newListItem.setThumbnailImage(thumbnailPath)
            
            return (url, newListItem, True)
        except (Exception) as exception:
            if not isinstance(exception, LoggingException):
                exception = LoggingException.fromException(exception)

            # Error creating Search item
            exception.addLogMessage("Error creating Search item")
            raise exception

    #==============================================================================

    def AddAllLinks(self, listItems, html, listshows = False, autoThumbnails = False):
        htmlparser = HTMLParser.HTMLParser()
        
        try:
            for link in html.findAll(u'a'):
                page = link[u'href']
                newLabel = htmlparser.unescape(link.contents[0])
                thumbnailPath = self.GetThumbnailPath(newLabel.replace(u' ', u''))
                newListItem = { 'label' : newLabel,
                                'thumbnail' : thumbnailPath }
#                newListItem = xbmcgui.ListItem( label=newLabel)
#                newListItem.setThumbnailImage(thumbnailPath)
    
                url = self.GetURLStart() + u'&page=' + mycgi.URLEscape(page)
    
                # "Most Popular" does not need a submenu, go straight to episode listing
                if listshows or u"Popular" in newLabel:
                    url = url + u'&listshows=1'
    
                logger.debug(u"url: %s" % url)
                listItems.append( (url,newListItem,True) )

            return True
        except (Exception) as exception:
            if not isinstance(exception, LoggingException):
                exception = LoggingException.fromException(exception)

            if html is not None:
                msg = "html:\n\n%s\n\n" % html
                exception.addLogMessage(msg)
                
            # Error adding links
            exception.addLogMessage("Error adding links")
            exception.process(severity = self.logLevel(logging.ERROR))
            return False

    #==============================================================================

    def ListAToZ(self, atozTable):
        logger.debug(u"")
        listItems = []

        if False == self.AddAllLinks(listItems, atozTable, listshows = True):
            return False        

#        xbmcplugin.addDirectoryItems( handle=self.pluginHandle, items=listItems )
#        xbmcplugin.endOfDirectory( handle=self.pluginHandle, succeeded=True )
#
#        return True
        return listItems
        
    #==============================================================================

    def ListSubMenu(self, html):
        htmlparser = HTMLParser.HTMLParser()
        try:
            soup = BeautifulSoup(html, selfClosingTags=[u'img'])
            aside = soup.find(u'aside')
    
            if aside is None:
                return self.ListLatest(soup)
    
            atozTable = soup.find(u'table', u'a-to-z')
            
            if atozTable is not None:
                return self.ListAToZ(atozTable)
    
            listItems = []
    
            categories = aside.findAll(u'a')
            for category in categories:
                href = category[u'href']
                
                title = htmlparser.unescape(category.contents[0])
    
                newListItem = { 'label' : title,
                                'thumbnail' : title.replace(" ", "") }
#                newListItem = xbmcgui.ListItem( label=title )
#                newListItem.setThumbnailImage(title.replace(u' ', u''))
                url = self.GetURLStart() + u'&page=' + mycgi.URLEscape(href) + u'&listshows=1'
                listItems.append( (url, newListItem, True) )
                logger.debug(u"url: %s" % url)
            
#            xbmcplugin.addDirectoryItems( handle=self.pluginHandle, items=listItems )
#            xbmcplugin.endOfDirectory( handle=self.pluginHandle, succeeded=True )
#    
#            return True
            return listItems
        except (Exception) as exception:
            if not isinstance(exception, LoggingException):
                exception = LoggingException.fromException(exception)

            if html is not None:
                msg = "html:\n\n%s\n\n" % html
                exception.addLogMessage(msg)
                
            # Error listing submenu
            exception.addLogMessage("Error listing submenu")
            exception.process(severity = self.logLevel(logging.ERROR))
            return False

    #==============================================================================
    
    def ListLatest(self, soup):
        logger.debug(u"")
        listItems = []
    
        calendar = soup.find(u'table', u'calendar')
    
        links = calendar.findAll(u'a')
        links.reverse()

        # Today
        page = links[0][u'href']
        newLabel = u"Today"
        newListItem = { 'label' : newLabel }
#        newListItem = xbmcgui.ListItem( label=newLabel )
        match=re.search( u"/([0-9][0-9][0-9][0-9]-[0-9][0-9]?-[0-9][0-9]?)/", page)
        if match is None:
            logger.warning(u"No date match for page href: '%s'" % page)
        else:
            url = self.GetURLStart() + u'&page=' + mycgi.URLEscape(page) + u'&listshows=1'
            listItems.append( (url,newListItem,True) )
            
        # Yesterday
        page = links[1][u'href']
        newLabel = u"Yesterday"
        newListItem = { 'label' : newLabel }
#        newListItem = xbmcgui.ListItem( label=newLabel )
        match=re.search( u"/([0-9][0-9][0-9][0-9]-[0-9][0-9]?-[0-9][0-9]?)/", page)
        if match is None:
            self.log(u"No date match for page href: '%s'" % page, logging.WARNING)
        else:
            url = self.GetURLStart() + u'&page=' + mycgi.URLEscape(page) + u'&listshows=1'
            listItems.append( (url,newListItem,True) )
        
        # Weekday
        page = links[2][u'href']
        match=re.search( u"/([0-9][0-9][0-9][0-9]-[0-9][0-9]?-[0-9][0-9]?)/", page)
        if match is None:
            logger.warning(u"No date match for page href: '%s'" % page)
        else:
            linkDate = date.fromtimestamp(mktime(strptime(match.group(1), u"%Y-%m-%d")))
                
            newLabel = linkDate.strftime(u"%A")
            newListItem = { 'label' : newLabel }
#            newListItem = xbmcgui.ListItem( label=newLabel )

            url = self.GetURLStart() + u'&page=' + mycgi.URLEscape(page) + u'&listshows=1'
            listItems.append( (url,newListItem,True) )
        
        # Weekday
        page = links[3][u'href']
        match=re.search( u"/([0-9][0-9][0-9][0-9]-[0-9][0-9]?-[0-9][0-9]?)/", page)
        if match is None:
            logger.warning(u"No date match for page href: '%s'" % page)
        else:
            linkDate = date.fromtimestamp(mktime(strptime(match.group(1), u"%Y-%m-%d")))
                
            newLabel = linkDate.strftime(u"%A")
            newListItem = { 'label' : newLabel }
#            newListItem = xbmcgui.ListItem( label=newLabel )

            url = self.GetURLStart() + u'&page=' + mycgi.URLEscape(page) + u'&listshows=1'
            listItems.append( (url,newListItem,True) )
        
        for link in links[4:]:
            page = link[u'href']
    
            match=re.search( u"/([0-9][0-9][0-9][0-9]-[0-9][0-9]?-[0-9][0-9]?)/", page)
            if match is None:
                logger.warning(u"No date match for page href: '%s'" % page)
                continue;
    
            linkDate = date.fromtimestamp(mktime(strptime(match.group(1), u"%Y-%m-%d")))
            
            newLabel = linkDate.strftime(u"%A, %d %B %Y")
            newListItem = { 'label' : newLabel }
#            newListItem = xbmcgui.ListItem( label=newLabel)
    
            url = self.GetURLStart() + u'&page=' + mycgi.URLEscape(page) + u'&listshows=1'
            listItems.append( (url,newListItem,True) )
    
#        xbmcplugin.addDirectoryItems( handle=self.pluginHandle, items=listItems )
#        xbmcplugin.endOfDirectory( handle=self.pluginHandle, succeeded=True )
        
#        return True
        return listItems
    
    
    #==============================================================================
    
    def AddEpisodeToList(self, listItems, episode):
        logger.debug(u"")
        
        try:
            htmlparser = HTMLParser.HTMLParser()
    
            href = episode[u'href']
            title = htmlparser.unescape( episode.find(u'span', u"thumbnail-title").contents[0] )
            date = episode.find(u'span', u"thumbnail-date").contents[0]                    
            #description = ...
            thumbnail = episode.find(u'img', u'thumbnail')[u'src']
        
            newLabel = title + u", " + date
                                            
            if self.config.get("RTE", 'descriptions', "True" ) == 'True':
                infoLabels = self.GetEpisodeInfo(self.GetEpisodeIdFromURL(href))
            else:
                infoLabels = {u'Title': newLabel, u'Plot': title}
            
            
            logger.debug(u"label == " + newLabel)
        
            if u"episodes available" in date:
                url = self.GetURLStart()  + u'&listavailable=1' + u'&page=' + mycgi.URLEscape(href)
 
                newListItem = { 'label' : newLabel, 'thumbnail' : thumbnail,
                                'videoInfo' : infoLabels }
#                newListItem = xbmcgui.ListItem( label=newLabel )
#                newListItem.setThumbnailImage(thumbnail)
#                newListItem.setInfo(u'video', infoLabels)

                folder = True
            else:
                #newListItem.setProperty('IsPlayable', 'true')

                folder = False
                match = re.search( u"/player/[^/]+/show/([0-9]+)/", href )
                if match is None:
                    logger.warning(u"No show id found in page href: '%s'" % href)
                    return
            
                episodeId = match.group(1)
        
                url = self.GetURLStart() + u'&episodeId=' +  mycgi.URLEscape(episodeId)
        
                contextMenuItems = []
                newListItem = self.ResumeWatchListItem(url, episodeId, contextMenuItems, infoLabels, thumbnail)
                    
            listItems.append( (url, newListItem, folder) )
        except (Exception) as exception:
            if not isinstance(exception, LoggingException):
                exception = LoggingException.fromException(exception)

            msg = u"episode:\n\n%s\n\n" % utils.drepr(episode)
            exception.addLogMessage(msg)

            # Error getting episode details
            exception.addLogMessage("Error getting episode details")
            exception.process(self.logLevel(logging.WARNING))
                   
    
    
    #==============================================================================
    
    def ListShows(self, html):
        logger.debug(u"")
        listItems = []
    
        try:
            soup = BeautifulSoup(html, selfClosingTags=[u'img'])
            episodes = soup.findAll(u'a', u"thumbnail-programme-link")

            for episode in episodes:
                self.AddEpisodeToList(listItems, episode)

#            xbmcplugin.addDirectoryItems( handle=self.pluginHandle, items=listItems )
#            xbmcplugin.endOfDirectory( handle=self.pluginHandle, succeeded=True )
    
#            return True
            return listItems
        except (Exception) as exception:
            if not isinstance(exception, LoggingException):
                exception = LoggingException.fromException(exception)
    
            if html is not None:
                msg = "html:\n\n%s\n\n" % html
                exception.addLogMessage(msg)
                
            # Error getting list of shows
            exception.addLogMessage("Error getting list of shows")
            # Error getting list of shows
            exception.process(severity = self.logLevel(logging.ERROR))
            return False
    
    
    #==============================================================================
    def GetTextFromElement(self, element):
        textList = element.contents
        text = u""
        
        for segment in textList:
            text = text + segment.string
                
        htmlparser = HTMLParser.HTMLParser()
        return htmlparser.unescape(text)    
        
        
    def AddEpisodeToSearchList(self, listItems, article):
        """
        <article class="search-result clearfix"><a
                href="/player/ie/show/10098947/" class="thumbnail-programme-link"><span
                    class="sprite thumbnail-icon-play">Watch Now</span><img class="thumbnail" alt="Watch Now"
                    src="http://img.rasset.ie/0006d29f-261.jpg"></a>
            <h3 class="search-programme-title"><a href="/player/ie/show/10098947/">Nuacht and <span class="search-highlight">News</span> with Signing</a></h3>
            <p class="search-programme-episodes"><a href="/player/ie/show/10098947/">Sun 30 Dec 2012</a></p>
            <!-- p class="search-programme-date">30/12/2012</p -->
            <p class="search-programme-description">Nuacht and <span class="search-highlight">News</span> with Signing.</p>
            <span class="sprite logo-rte-one search-channel-icon">RTÉ 1</span>
        </article>
        """

        episodeLink = article.find(u'a', u"thumbnail-programme-link")
        href = episodeLink[u'href']
    
        title = self.GetTextFromElement( article.find(u'h3', u"search-programme-title").a )
        dateShown = article.findNextSibling(u'p', u"search-programme-episodes").a.text
        description = self.GetTextFromElement( article.findNextSibling(u'p', u"search-programme-description") )
        thumbnail = article.find('img', 'thumbnail')['src']
        
        title = title + u' [' + dateShown + u']'
    
        infoLabels = {u'Title': title, u'Plot': description, u'PlotOutline': description, 'pubDate' : dateShown}

        match = re.search( u"/player/[^/]+/show/([0-9]+)/", href )
        if match is None:
            self.log(u"No show id found in page href: '%s'" % href, logging.WARNING)
            return
    
        episodeId = match.group(1)
    
        url = self.GetURLStart() + u'&episodeId=' +  mycgi.URLEscape(episodeId)

        contextMenuItems = []
        newListItem = { 'label' : title, 'episodeId' : episodeId,
                        'thumbnail' : thumbnail, "Video" : True,
                        'contextMenuItems' : contextMenuItems,
                        'videoInfo' : infoLabels, 'url' : url }
        #self.ResumeWatchListItem(url, episodeId, contextMenuItems, infoLabels, thumbnail)    
            
        listItems.append( (url, newListItem, True) )
        
    #==============================================================================
    
    def ListSearchShows(self, html):
        logger.debug(u"")
        listItems = []
        
        try:
            soup = BeautifulSoup(html, selfClosingTags=[u'img'])
            articles = soup.findAll(u"article", u"search-result clearfix")
        
            if len(articles) > 0:
                for article in articles:
                    self.AddEpisodeToSearchList(listItems, article)
    
                current = soup.find('li', 'dot-current')
                
                if current is not None:
                    moreResults = current.findNextSibling('li', 'dot')
                    
                    if moreResults is not None:
                        try:
                            listItems.append( self.CreateSearchItem(moreResults.a['href']) )
                        except (Exception) as exception:
                            if not isinstance(exception, LoggingException):
                                exception = LoggingException.fromException(exception)
            
                            # Not fatal, just means that we don't have the search option
                            exception.process(severity = self.logLevel(logging.WARNING))
                
        
#            xbmcplugin.addDirectoryItems( handle=self.pluginHandle, items=listItems )
#            xbmcplugin.endOfDirectory( handle=self.pluginHandle, succeeded=True )
        
#            return True
            return listItems
        except (Exception) as exception:
            if not isinstance(exception, LoggingException):
                exception = LoggingException.fromException(exception)
        
            if html is not None:
                msg = "html:\n\n%s\n\n" % html
                exception.addLogMessage(msg)
                
            # Error getting list of shows
            exception.addLogMessage("Error getting list of shows")
            exception.process(severity = self.logLevel(logging.ERROR))
            return False

    #==============================================================================
    
    def ListAvailable(self, html):
        logger.debug(u"")
        listItems = []
        
        try:        
            soup = BeautifulSoup(html, selfClosingTags=[u'img'])
            count = int(soup.find(u'meta', { u'name' : u"episodes_available"} )[u'content'])
    
            availableEpisodes = soup.findAll(u'a', u"thumbnail-programme-link")
        
            for index in range ( 0, count ):
                self.AddEpisodeToList(listItems, availableEpisodes[index])
    
#            xbmcplugin.addDirectoryItems( handle=self.pluginHandle, items=listItems )
#            xbmcplugin.endOfDirectory( handle=self.pluginHandle, succeeded=True )
    
#            return True
            return listItems
        except (Exception) as exception:
            if not isinstance(exception, LoggingException):
                exception = LoggingException.fromException(exception)
    
            if html is not None:
                msg = "html:\n\n%s\n\n" % html
                exception.addLogMessage(msg)
                
            # Error getting count of available episodes
            exception.addLogMessage("Error getting count of available episodes")
            exception.process("Cannot show available episodes", "Error getting count of available episodes", self.logLevel(logging.ERROR))
            return False
    
    #==============================================================================
    
    def GetSWFPlayer(self):
        logger.debug(u"")
        
        try:
            xml = self.httpManager.GetWebPage(configUrl, 20000)
            soup = BeautifulStoneSoup(xml)
            
            swfPlayer = soup.find("player")['url']

            if swfPlayer.find('.swf') > 0:
                swfPlayer=re.search("(.*\.swf)", swfPlayer).groups()[0]
                
            if swfPlayer.find('http') == 0:
                # It's an absolute URL, do nothing.
                pass
            elif swfPlayer.find('/') == 0:
                # If it's a root URL, append it to the base URL:
                swfPlayer = urljoin(urlRoot, swfPlayer)
            else:
                # URL is relative to config.xml 
                swfPlayer = urljoin(configUrl, swfPlayer)
                
            return swfPlayer
        
        except (Exception) as exception:
            if not isinstance(exception, LoggingException):
                exception = LoggingException.fromException(exception)

            # Unable to determine swfPlayer URL. Using default: %s
            exception.addLogMessage("Unable to determine swfPlayer URL. Using default: %s" % swfDefault)
            exception.process(severity = self.logLevel(logging.WARNING))
            return swfDefault

    
    def GetLiveSWFPlayer(self):
        logging.debug(u"")
    
        return swfLiveDefault

    #==============================================================================

    def GetThumbnailFromEpisode(self, episodeId, soup = None):
        logging.debug(u"")

        try:
            html = None
            if soup is None:
                html = self.httpManager.GetWebPage(showUrl % episodeId, 20000)
                soup = BeautifulSoup(html, selfClosingTags=[u'img'])
            
            image = soup.find(u'meta', { u'property' : u"og:image"} )[u'content']
            return image
        
        except (Exception) as exception:
            if not isinstance(exception, LoggingException):
                exception = LoggingException.fromException(exception)
            
            if html is not None:
                msg = "html:\n\n%s\n\n" % html
                exception.addLogMessage(msg)
                
            # Error processing web page
            exception.addLogMessage("Error processing web page: " + (showUrl % episodeId))
            exception.process(u"Error getting thumbnail", "", self.logLevel(logging.WARNING))
            raise exception
    

    #==============================================================================
    
    def GetEpisodeInfo(self, episodeId, soup = None):
        logger.debug(u"")

        infoLabels = { 'grabber' : 'irishtv',
                       'scraperName' : self.GetProviderId(),
                       'timestamp' : time(),
                       'id' : episodeId }
    
        try:
            html = None
            if soup is None:
                html = self.httpManager.GetWebPage(showUrl % episodeId, 20000)
                soup = BeautifulSoup(html, selfClosingTags=[u'img'])

            meta = soup.findAll(u'meta')
            for item in meta:
                name = item.get('name')
                if not name:
                    continue
                if name in episodeMap:
                    infoLabels[episodeMap[name]] = item['content']

            if 'duration' in infoLabels:
                duration = float(infoLabels['duration']) / 1000.0
                infoLabels['duration'] = duration

        except (Exception) as exception:
            if not isinstance(exception, LoggingException):
                exception = LoggingException.fromException(exception)
    
            if html is not None:
                msg = "html:\n\n%s\n\n" % html
                exception.addLogMessage(msg)
                
            # Error processing web page %s
            exception.addLogMessage("Error processing web page: " + (showUrl % episodeId))
            exception.process(u"Error getting episode information", "", self.logLevel(logging.WARNING))
    
        if not 'Title' in infoLabels or not infoLabels['Title']:
            infoLabels['Title'] = 'Unknown ' + episodeId
        
        logger.debug(u"Title: %s" % infoLabels['Title'])
        logger.debug(u"infoLabels: %s" % infoLabels)
        return infoLabels
    
    #==============================================================================
    
    def PlayEpisode(self, episodeId, resumeFlag):
        logger.debug(u"%s" % episodeId)
        
        # "Getting SWF url"
        logger.info("Getting stream url")
        swfPlayer = self.GetSWFPlayer()
    
        try:
#            if self.dialog.iscanceled():
#                return False
            # "Getting episode web page"
            logger.info("Getting episode web page")
            feedProcessStatus = 0
            html = None
            html = self.httpManager.GetWebPage(showUrl % episodeId, 20000)
    
            soup = BeautifulSoup(html, selfClosingTags=[u'img'])
            feedsPrefix = soup.find(u'meta', { u'name' : u"feeds-prefix"} )[u'content']

#            if self.dialog.iscanceled():
#                return False
            # "Getting episode info"
            logger.info("Getting episode information")
            infoLabels = self.GetEpisodeInfo(episodeId, soup)
            thumbnail = self.GetThumbnailFromEpisode(episodeId, soup)
    
            urlGroups = None
            feedProcessStatus = 1

#            if self.dialog.iscanceled():
#                return False
            # "Getting playpath data"
            logger.info("Getting playpath data")
            urlGroups = self.GetStringFromURL(feedsPrefix + episodeId, u"\"url\": \"(/[0-9][0-9][0-9][0-9]/[0-9][0-9][0-9][0-9]/)([a-zA-Z0-9]+/)?(.+?)(?:/manifest)?.f4m\"", 20000)
            feedProcessStatus = 2
            if urlGroups is None:
                # Log error
                logger.error(u"urlGroups is None")
                return False
    
            (urlDateSegment, extraSegment, urlSegment) = urlGroups
            logger.info("urlGroups: %s" % list(urlGroups))
    
            rtmpStr = u"rtmpe://fmsod.rte.ie/rtevod"
            app = u"rtevod"
            swfVfy = swfPlayer
            playPath = u"mp4:%s%s/%s_512k.mp4" % (urlDateSegment, urlSegment, urlSegment)
            playURL = u"%s app=%s playpath=%s swfvfy=%s" % (rtmpStr, app, playPath, swfVfy)
    
            rtmpVar = rtmp.RTMP(rtmp = rtmpStr, app = app, swfVfy = swfVfy, playPath = playPath)
            self.AddSocksToRTMP(rtmpVar)
            defaultFilename = self.GetDefaultFilename(infoLabels[u'Title'], episodeId)
            infoLabels['filename'] = defaultFilename
    
            logger.debug(u"(%s) playUrl: %s" % (episodeId, playURL))
            
            return self.PlayOrDownloadEpisode(infoLabels, thumbnail, rtmpVar, defaultFilename, url = None, subtitles = None, resumeKey = episodeId, resumeFlag = resumeFlag)
        except (Exception) as exception:
            if not isinstance(exception, LoggingException):
                exception = LoggingException.fromException(exception)
    
            if html is not None:
                msg = "html:\n\n%s\n\n" % html
                exception.addLogMessage(msg)
            
            if feedProcessStatus == 1:
                # Exception while getting data from feed
                try:
                    feedUrl = 'http://feeds.rasset.ie/rteavgen/player/playlist/?itemId=%s&type=iptv&format=xml' % episodeId
                    html = self.httpManager.GetWebPageDirect(feedUrl)
                    
                    msg = "html:\n\n%s\n\n" % html
                    exception.addLogMessage(msg)
                except:
                    exception.addLogMessage("Execption getting " + feedUrl)

                try:
                    feedUrl = 'http://feeds.rasset.ie/rteavgen/player/playlist/?itemId=%s&type=iptv1&format=xml' % episodeId
                    html = self.httpManager.GetWebPageDirect(feedUrl)
                    
                    msg = "html:\n\n%s\n\n" % html
                    exception.addLogMessage(msg)
                except:
                    exception.addLogMessage("Execption getting " + feedUrl)
            # Error playing or downloading episode %s
            exception.addLogMessage("Error playing or downloading episode %s" % episodeId)
            # Error playing or downloading episode %s
            exception.process("Error playing or downloading episode %s" % ' ' , '', self.logLevel(logging.ERROR))
            return False
    

    def PlayLiveTV(self, html, dummy):
        """
          <li class="first-live-channel selected-channel">
              <a href="/player/ie/live/8/" class="live-channel-container">
              <span class="sprite live-logo-rte-one">RTÉ One</span>
              
                  <span class="sprite live-channel-now-playing">Playing</span>
              
              <span class="live-channel-info"><span class="live-time">Now:</span>The Works</span>
              <span class="live-channel-info"><span class="live-time">Next:</span>RTÉ News: Nine O&#39;Clock and Weather (21:00)</span></a>
          </li>
          
        """
        logger.debug(u"")
        
        swfPlayer = self.GetLiveSWFPlayer()
    
        liveChannels = {
                      u'RT\xc9 One' : u'rte1',
                      u'RT\xc9 Two' : u'rte2',
                      u'RT\xc9jr': u'rtejr',
                      u'RT\xc9 News Now' : u'newsnow'
                      }
        
        try:
            soup = BeautifulSoup(html, selfClosingTags=[u'img'])
            #liveTVInfo = soup.find('span', 'sprite live-channel-now-playing').parent
            liveTVInfo = soup.find('li', 'selected-channel')
            channel = liveTVInfo.find('span').string
            programme = liveTVInfo.find('span', 'live-channel-info').next.nextSibling
            programme = self.fullDecode(programme).replace('&#39;', "'")
            
            infoLabels = {u'Title': channel + u": " + programme }
            thumbnailPath = self.GetThumbnailPath((channel.replace(u'RT\xc9 ', '')).replace(' ', ''))
            
            rtmpStr = u"rtmp://fmsod.rte.ie/live/"
            app = u"live"
            swfVfy = swfPlayer
            playPath = liveChannels[channel]
    
            rtmpVar = rtmp.RTMP(rtmp = rtmpStr, app = app, swfVfy = swfVfy, playPath = playPath, live = True)
            self.AddSocksToRTMP(rtmpVar)
            
            self.Play(infoLabels, thumbnailPath, rtmpVar)
            
            return True
        except (Exception) as exception:
            if not isinstance(exception, LoggingException):
                exception = LoggingException.fromException(exception)
    
            if html is not None:
                msg = "html:\n\n%s\n\n" % html
                exception.addLogMessage(msg)
                
            # Error playing live TV
            exception.addLogMessage("Error playing Live TV")
            exception.process(severity = self.logLevel(logging.ERROR))
            return False
    


    def GetEpisodeIdFromURL(self, url):
        segments = url.split(u"/")
        segments.reverse()
    
        for segment in segments:
            if segment <> u'':
                return segment
    
    #==============================================================================
    def GetDefaultFilename(self, title, episodeId):
        if episodeId <> u"":
            #E.g. NAME.s01e12
            return title + u"_" + episodeId
    
        return title
    
   #==============================================================================
    def GetPlayerJSURL(self, html):
        try:
            soup = BeautifulSoup(html, selfClosingTags=[u'img'])
            # E.g. <script src="http://static.rasset.ie/static/player/js/player.js?v=3"></script>
            script = soup.find(src=re.compile("player.\js\?"))
        
            playerJS = script['src']
        
        except (Exception) as exception:
            if not isinstance(exception, LoggingException):
                exception = LoggingException.fromException(exception)
    
            if html is not None:
                msg = "html:\n\n%s\n\n" % html
                exception.addLogMessage(msg)
                
            # Error getting player.js url: Using default %s
            exception.addLogMessage("Error getting player.js url: Using default %s" % playerJSDefault)
            exception.process(severity = self.logLevel(logging.WARNING))
            playerJS = playerJSDefault

        return playerJS
        
        
    def GetPlayer(self, pid, live, playerName):
#        if self.watchedEnabled:
#            player = WatchedPlayer()
#            player.initialise(live, playerName, self.GetWatchedPercent(), pid, self.resumeEnabled, self.log)
#            return player
#        elif self.resumeEnabled:
#            player = ResumePlayer()
#            player.init(pid, live, self.GetProviderId())
#            return player
        
        return super(RTEProvider, self).GetPlayer(pid, live, self.GetProviderId())

    def GetSearchURL(self):
        try:
            rootMenuHtml = None
            html = None
            rootMenuHtml = self.httpManager.GetWebPage(rootMenuUrl, 60)
            playerJSUrl = self.GetPlayerJSURL(rootMenuHtml)
            
            html = self.httpManager.GetWebPage(playerJSUrl, 20000)

            programmeSearchIndex = html.find('Programme Search')
            match=re.search("window.location.href = \'(.*?)\'", html[programmeSearchIndex:])
            searchURL = match.group(1)
        
        except (Exception) as exception:
            if not isinstance(exception, LoggingException):
                exception = LoggingException.fromException(exception)
    
            if rootMenuHtml is not None:
                msg = "rootMenuHtml:\n\n%s\n\n" % rootMenuHtml
                exception.addLogMessage(msg)
                
            if html is not None:
                msg = "html:\n\n%s\n\n" % html
                exception.addLogMessage(msg)
                
            # Error getting search url: Using default %s
            exception.addLogMessage("Error getting search url: Using default %s" % searchUrlDefault)
            exception.process(severity = self.logLevel(logging.WARNING))
            searchURL = searchUrlDefault

        return searchURL
        
    def DoSearchQuery( self, query = None, queryUrl = None):
        if query is not None:
            queryUrl = urlRoot + self.GetSearchURL() + mycgi.URLEscape(query)
             
        logger.debug(u"queryUrl: %s" % queryUrl)
        try:
            html = None
            html = self.httpManager.GetWebPage( queryUrl, 1800 )
            if html is None or html == '':
                # Data returned from web page: %s, is: '%s'
                logException = LoggingException(logMessage = "Data returned from web page: %s, is: '%s'" % ( __SEARCH__ + mycgi.URLEscape(query), html))
    
                # Error getting web page
                logException.process("Error getting web page", u'', severity = self.logLevel(logging.WARNING))
                return False
    
            return self.ListSearchShows(html)
        except (Exception) as exception:
            if not isinstance(exception, LoggingException):
                exception = LoggingException.fromException(exception)
    
            if html is not None:
                msg = "html:\n\n%s\n\n" % html
                exception.addLogMessage(msg)
                
            # Error performing query %s
            exception.addLogMessage("Error performing query %s" % query)
            exception.process(severity = self.logLevel(logging.ERROR))
            return False
        
