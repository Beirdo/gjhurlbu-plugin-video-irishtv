#! /usr/bin/python
# vim:ts=4:sw=4:ai:et:si:sts=4:fileencoding=utf-8
import re
import sys
from time import mktime,strptime,time
from datetime import timedelta
from datetime import date

#import xbmcplugin
#import xbmcgui
#import xbmc

import mycgi
import utils
from loggingexception import LoggingException
import rtmp
import zlib

from provider import Provider
#from resumeplayer import ResumePlayer
#from watched import WatchedPlayer


from BeautifulSoup import BeautifulSoup, NavigableString

import HTMLParser
import logging

logger = logging.getLogger(__name__)

urlRoot     = u"http://www.tv3.ie"
rootMenuUrl = u"http://www.tv3.ie/3player"
allShowsDefaultUrl  = u"http://www.tv3.ie/3player/allshows"
searchUrl = u"http://www.tv3.ie/player/assets/php/search.php"
calendarUrl = u"http://www.tv3.ie/player/assets/php/calendar.php"
swfDefault = u"http://www.tv3.ie/player/assets/flowplayer/flash/flowplayer.commercial-3.2.7.swf"

metaMap = { "og:title" : "Title", "og:description" : "Plot",
            "og:site_name" : "station", "og:image" : "thumbnail" }
labelMap = { "Broadcast:" : "pubDate", "Duration:" : "duration" }

class TV3Provider(Provider):

#    def __init__(self):
#        self.cache = cache

    def GetProviderId(self):
        return u"TV3"

    def GetPlayer(self, pid, live, playerName):
#        if self.watchedEnabled:
#            player = WatchedPlayer()
#            player.initialise(live, playerName, self.GetWatchedPercent(), pid, self.resumeEnabled, self.log)
#            return player
#        elif self.resumeEnabled:
#            player = ResumePlayer()
#            player.init(pid, live, playerName)
#            return player
        
        return super(TV3Provider, self).GetPlayer(pid, live, playerName)

    def ExecuteCommand(self, mycgi):
        return super(TV3Provider, self).ExecuteCommand(mycgi)

    def ShowRootMenu(self):
        logger.debug(u"")
        try:
            html = None
            html = self.httpManager.GetWebPage(rootMenuUrl, 300)
    
            if html is None or html == u'':
                # Error getting %s Player "Home" page
                logException = LoggingException(logMessage = "Error getting %s Player Home page" % self.GetProviderId())
                # 'Cannot show TV3 root menu', Error getting TV3 Player "Home" page
                logException.process("Cannot show TV3 root menu", "Error getting %s Player Home page" % self.GetProviderId(), self.logLevel(logging.ERROR))
                #raise logException
                return False
    
            #soup = BeautifulSoup(html, selfClosingTags=['img'])
            categories = self.GetCategories(html)
    
            if len(categories) == 0:
                # "Can't find dropdown-programmes"
                logException = LoggingException(logMessage = "Can't find dropdown-programmes")
                # 'Cannot show TV3 root menu', Error parsing web page
                logException.process("Cannot show TV3 root menu", "Error processing web page", self.logLevel(logging.ERROR))
                #raise logException
                return False
            
            listItems = []
    
            # Search
            newLabel = "Search"
            thumbnailPath = self.GetThumbnailPath(newLabel)
            newListItem = { 'label' : newLabel, 'thumbnail' : thumbnailPath }
#            newListItem = xbmcgui.ListItem( label=newLabel )
#            newListItem.setThumbnailImage(thumbnailPath)
            url = self.GetURLStart() + u'&search=1'
            listItems.append( (url, newListItem, True) )
    
#            self.AddFeatured(listItems, html)        
            self.AddCategories(listItems, categories)        
    
            # All Shows - A to Z
            newLabel = "All Shows - A to Z"
            thumbnailPath = self.GetThumbnailPath(newLabel)
            newListItem = { 'label' : newLabel, 'thumbnail' : thumbnailPath }
#            newListItem = xbmcgui.ListItem( label=newLabel )
#            newListItem.setThumbnailImage(thumbnailPath)
            url = self.GetURLStart() + u'&allShows=1'
            listItems.append( (url, newListItem, True) )

            # All Shows - By Date
            newLabel = "All Shows - By Date"
            thumbnailPath = self.GetThumbnailPath(newLabel)
            newListItem = { 'label' : newLabel, 'thumbnail' : thumbnailPath }
#            newListItem = xbmcgui.ListItem( label=newLabel )
#            newListItem.setThumbnailImage(thumbnailPath)
            url = self.GetURLStart() + u'&calendar=1'
            listItems.append( (url, newListItem, True) )
    
#            xbmcplugin.addDirectoryItems( handle=self.pluginHandle, items=listItems )
#            xbmcplugin.endOfDirectory( handle=self.pluginHandle, succeeded=True )
        except (Exception) as exception:
            if not isinstance(exception, LoggingException):
                exception = LoggingException.fromException(exception)

            if html is not None:
                msg = u"html:\n\n%s\n\n" % html
                exception.addLogMessage(msg)
                
            # Cannot show root menu
            exception.addLogMessage("Cannot show root menu")
            exception.process(severity = self.logLevel(logging.ERROR))
            return False

        return listItems

    # listshows: If '1' list the shows on the main page, otherwise process the sidebar. The main page links to programmes or specific episodes, the sidebar links to categories or sub-categories
    # listavailable: If '1' process the specified episode as one of at least one episodes availabe, i.e. list all episodes available
    # search: If '1' perform a search
    # episodeId: url, relative to www.tv3.ie, to be processed

    def ParseCommand(self, mycgi):
        (category, search, allShows, calendar, date, page, thumbnail, resume) = mycgi.Params( u'category', u'search', u'allShows', u'calendar', u'date', u'page', u'thumbnail', u'resume' )
        logger.debug(u"category: %s, search: %s, allShows: %s, calendar: %s, date: %s, page: %s, thumbnail: %s, resume: %s" % (category, str(search), str(allShows), calendar, date, page, thumbnail, str(resume)))

        if search <> u'':
            return self.DoSearch(search)
        
        if category <> u'':
            return self.ShowCategory(category)

        if allShows <> u'':
            if thumbnail <> u'':
                return self.ListAToZ(thumbnail)
            else:
                return self.ListAToZ()

        if calendar <> u'':
            return self.ListCalendar()
            
        if date <> u'':
            return self.ListByDate(date)
            
        if page == u'':
            # "Can't find 'page' parameter "
            logException = LoggingException(logMessage = "Cannot find 'page' parameter")
            # 'Cannot proceed', Error processing command
            logException.process("Cannot proceed", "Error processing web page", self.logLevel(logging.ERROR))
            return False

        logger.debug(u"page = %s" % page)
        page = mycgi.URLUnescape(page)
        logger.debug(u"mycgi.URLUnescape(page) = %s" % page)

        if u' ' in page:
            page = page.replace(u' ', u'%20')

        resumeFlag = False
        if resume <> u'':
            resumeFlag = True

        try:
            return self.PlayVideoWithDialog(self.PlayEpisode, (page, resumeFlag))
            
        except (Exception) as exception:
            if not isinstance(exception, LoggingException):
                exception = LoggingException.fromException(exception)
            
            # "Error playing or downloading episode %s"
            exception.addLogMessage("Error playing or downloading episode %s" % u"")
            # "Error processing video"
            exception.process(severity = self.logLevel(logging.ERROR))
            return False

                
    def GetCategories(self, html):
        categories = []

        soup = BeautifulSoup(html)
        categoryHTMLList = soup.findAll(u'h2')
        
        htmlparser = HTMLParser.HTMLParser()

        try:        
            for categoryHTML in categoryHTMLList:
                if categoryHTML.findNextSibling(u'div', {u'id':re.compile(u'^slider')}) is not None:
                    categories.append(unicode(htmlparser.unescape(categoryHTML.text)))
        except (Exception) as exception:
            exception = LoggingException.fromException(exception)
    
            # Error processing categories
            exception.addLogMessage("Error processing categories")
            exception.process(severity = self.logLevel(logging.WARNING))
            
        return categories
    
#    def AddFeatured(self, listItems, html):
#        soup = BeautifulSoup(html)

#        videos = soup.find('div', {'id':'acc-menu2'}).find('a', {'href':re.compile('^http://www.tv3')})
        
#        for video in videos:
#            video = 
#            newLabel = category
#            thumbnailPath = self.GetThumbnailPath(newLabel.replace(u' ', u''))
##            newListItem = xbmcgui.ListItem( label=newLabel)
#            newListItem.setThumbnailImage(thumbnailPath)

#            url = self.GetURLStart() + u'&category=' + mycgi.URLEscape(category)

#            self.log(u"url: %s" % url, xbmc.LOGDEBUG)
#            listItems.append( (url,newListItem,True) )
            

    def AddCategories(self, listItems, categories):
        for category in categories:
            newLabel = category
            thumbnailPath = self.GetThumbnailPath(newLabel.replace(u' ', u''))
            newListItem = { 'label' : newLabel, 'thumbnail' : thumbnailPath }
#            newListItem = xbmcgui.ListItem( label=newLabel)
#            newListItem.setThumbnailImage(thumbnailPath)

            url = self.GetURLStart() + u'&category=' + mycgi.URLEscape(category)

            logger.debug(u"url: %s" % url)
            listItems.append( (url,newListItem,True) )

    def GetNameFromGridshow(self, gridshow):
            try:
                htmlparser = HTMLParser.HTMLParser()
                return u'"' + re.search(u"3player\s+\|\s+(.+),\s+(\d\d/\d\d/\d\d\d\d)\.\s*(.*?)", htmlparser.unescape(gridshow.a['title'])).group(1) + '"'
            except (Exception) as exception:
                return u"programme"
        
    def ShowCategory(self, category):
        logger.debug(u"")
        html = None
        html = self.httpManager.GetWebPage(rootMenuUrl, 300)
        """
        <h2>Most Talked About</h2>
        ...
        <div id="slider1" ...>
            <ul style="width: 5892px; ">
                <li style="margin-left: -982px; float: left; ">
                    <div id="gridshow">
                        <a title="3player | Snog Marry Avoid, 22/11/2012. Jenny meets blonde Danielle, gothic geisha Azelie and outrageous mother Jay" href="http://www.tv3.ie/3player/show/452/56083/1/Snog-Marry-Avoid">
                            <img alt="3player | Snog Marry Avoid, 22/11/2012. Jenny meets blonde Danielle, gothic geisha Azelie and outrageous mother Jay" src="./3player   Home_files/snog_nov22_3player_1_56083_180x102.jpg" class="shadow smallroundcorner">
                        </a>
                        <h3>
                            <a title="3player | Snog Marry Avoid, 22/11/2012. Jenny meets blonde Danielle, gothic geisha Azelie and outrageous mother Jay" href="http://www.tv3.ie/3player/show/452/56083/1/Snog-Marry-Avoid">Snog Marry Avoid</a>
                        </h3>
                        <span id="gridcaption">Jenny meets blonde Danielle, gothic geisha Azelie and out...</span>
                        <span id="griddate">22/11/2012</span>
                        <span id="gridduration">00:23:24</span>
                    </div>
                    ...
        """
        htmlparser = HTMLParser.HTMLParser()

        listItems = []
        
        soup = BeautifulSoup(html)
        gridshows = soup.find(u'h2', text=category).parent.findNextSibling(u'div', {u'id':re.compile(u'^slider')}).findAll(u'div', {u'id':u'gridshow'})
        total = len(gridshows) 
        for gridshow in gridshows:
            try:
                infoLabels = self.GetEpisodeInfoCategory(gridshow)
                page = gridshow.a[u'href']
                thumbnail = gridshow.a.img[u'src']
                dot=gridshow.a['title'].index(u'.')
                newLabel=infoLabels[u'Title']
                
                self.AddEpisodeItem(newLabel, thumbnail, infoLabels, page, listItems)
            except (Exception) as exception:
                if not isinstance(exception, LoggingException):
                    exception = LoggingException.fromException(exception)

                programme = self.GetNameFromGridshow(gridshow)
                # "Error processing <programme>"
                exception.addLogMessage("Error processing %s" % programme + u"\n" + repr(gridshow))
                exception.process("Error processing %s" % programme, u"", logging.WARNING)
            
#        xbmcplugin.addDirectoryItems( handle=self.pluginHandle, items=listItems )
#        xbmcplugin.endOfDirectory( handle=self.pluginHandle, succeeded=True )
            
#        return True
        return listItems
    
#==============================================================================
    def AddEpisodeItem(self, label, thumbnail, infoLabels, page, listItems):
        label = label.replace(u'&#39;', u"'" )
        
        page = mycgi.URLUnescape(page)
        if u' ' in page:
            page = page.replace(u' ', u'%20')

        resumeKey = unicode(zlib.crc32(page))
        
        url = self.GetURLStart() + u'&episodeId=' + resumeKey + u'&page=' + mycgi.URLEscape(page)

        contextMenuItems = []
        newListItem = { 'label' : label, 'episodeId' : resumeKey,
                        'thumbnail' : thumbnail, 'Video' : True,
                        'contextMenuItems' : contextMenuItems,
                        'videoInfo' : infoLabels, 'url' : url }
#        newListItem = self.ResumeWatchListItem(url, resumeKey, contextMenuItems, infoLabels, thumbnail)
            
        listItems.append( (url, newListItem, False) )


    def GetAllShowsLink(self, soup): 
        logger.debug(u"")
        
        try:
            anchor = soup.find(u'div', {u'id':u'bottombar'}).find(lambda tag: tag.name == u'a' and tag.text == u'All Shows')
            return urlRoot + anchor[u'href']
        
        except (Exception) as exception:
            if not isinstance(exception, LoggingException):
                exception = LoggingException.fromException(exception)
            
            # Unable to determine "All Shows" URL. Using default: %s
            exception.addLogMessage("Unable to determine 'All Shows' URL.  Using default %s" % allShowsDefaultUrl)
            exception.process(severity = logging.WARNING)
            return allShowsDefaultUrl

    def AddAllShowListItem(self, title, video, listItems, thumbnail = None):
        date = video.find(u'span', {u'id':u'griddate'}).text
        title = title + u", " + date
        
        description = self.fullDecode(video.findAll(u'a')[1].text)
        infoLabels = {u'Title': title, u'Plot': description, u'PlotOutline': description}

        anchor = video.find(u'a')
        page = anchor[u'href']
        
        if thumbnail is None:
            thumbnail = anchor.img[u'src']

        self.AddEpisodeItem(title, thumbnail, infoLabels, page, listItems)

            
    def ListAToZ(self, page = None):
        logger.debug(u"")
        """
            <div id="g1" class="gridshow">
                <a href="javascript:void(0)">
                    <img src="./3player   All Shows_files/304_180x102.jpg" class="shadow smallroundcorner">
                </a>
                <h3>
                    <a href="http://www.tv3.ie/3player/show/304/0/0/24+Hours+To+Kill">24 Hours To Kill</a>
                </h3>
            </div>
        """

        try:
            html = None
            html = self.httpManager.GetWebPage(rootMenuUrl, 300)

            soup = BeautifulSoup(html)
            allShowsUrl = self.GetAllShowsLink(soup)
                        
            html = self.httpManager.GetWebPage(allShowsUrl, 1800)

            soup = BeautifulSoup(html)
            htmlparser = HTMLParser.HTMLParser()
            
            listItems = []
            
            if page is None:
                gridshows = soup.findAll(u'div', {u'class':re.compile(u'^gridshow')})
                for gridshow in gridshows:
                    try:
                        title = u''
                        thumbnailPath = gridshow.a.img[u'src']
                        tooltip = gridshow.a.img[u'title']
                        
                        soup = BeautifulSoup(tooltip)
                        videos = soup.findAll(u'div', {u'id':u'tooltip_showvideo'})
                        page = soup.find(u'a')[u'href']
                        slash = page.rindex(u'/')
                        title = page[slash+1:].replace(u'+',u' ')
                        title = self.fullDecode(title)
                        
                        # If there's just one episode then link directly to the episode
                        if len(videos) == 1:
                            self.AddAllShowListItem(title, videos[0], listItems, thumbnailPath)
                        else:                    
                            title = title + u", " + unicode(len(videos)) + u" episodes available"
                            
                            description = soup.find(u'div', {u'id':u'tooltip_showcontent'}).contents[0]
                            
                            if description is None or not isinstance(description, NavigableString):
                                description = u''
                            else:
                                description = self.fullDecode(description)
                            
                            infoLabels = {u'Title': title, u'Plot': description, u'PlotOutline': description}
        
                            newListItem = { 'label' : title,
                                            'thumbnail' : thumbnailPath,
                                            'videoInfo' : infoLabels }
#                            newListItem = xbmcgui.ListItem( label=title )
#                            newListItem.setInfo(u'video', infoLabels)
#                            newListItem.setThumbnailImage(thumbnailPath)
            
                            url = self.GetURLStart() + u'&thumbnail=' + mycgi.URLEscape(thumbnailPath) + u'&allShows=1'
                            listItems.append( (url,newListItem,True) )
                    except (Exception) as exception:
                        if not isinstance(exception, LoggingException):
                            exception = LoggingException.fromException(exception)
                        
                        programme = self.GetNameFromGridshow(gridshow)
                        # "Error processing <programme>"
                        exception.addLogMessage(logMessage = "Error processing %s" % programme + u"\n" + repr(gridshow))
                        exception.process("Error processing %s" % programme, "", logging.WARNING)
                        
            else:
                imageTag = soup.find(src=page)
                tooltip = imageTag[u'title']
                
                soup = BeautifulSoup(tooltip)
                videos = soup.findAll(u'div', {u'id':u'tooltip_showvideo'})
                page = soup.find(u'a')[u'href']
                slash = page.rindex(u'/')
                title = page[slash+1:].replace(u'+',u' ')
                title = self.fullDecode(title) 
                 
                for video in videos:
                    try:
                          self.AddAllShowListItem(title, video, listItems)
                    except (Exception) as exception:
                        if not isinstance(exception, LoggingException):
                            exception = LoggingException.fromException(exception)
                        
                        # "Error processing <programme>"
                        exception.addLogMessage(logMessage = "Error processing %s"% title + u"\n" + repr(video))
                        exception.process("Error processing %s" % title, u"", logging.WARNING)
                        

#            xbmcplugin.addDirectoryItems( handle=self.pluginHandle, items=listItems )
#            xbmcplugin.endOfDirectory( handle=self.pluginHandle, succeeded=True )
        except (Exception) as exception:
            if not isinstance(exception, LoggingException):
                exception = LoggingException.fromException(exception)

            if html is not None:
                msg = u"html:\n\n%s\n\n" % html
                exception.addLogMessage(msg)
                
            # Error processing "Show All" menu
            exception.addLogMessage("Error processing 'Show All' menu")
            exception.process(severity = self.logLevel(logging.ERROR))
            return False

        return listItems
        
#==============================================================================
    def AddEpisodeToSearchList(self, listItems, video):
        page = re.search(u'gotopage\("(.+?)"\);', video[u'onclick']).group(1)

        title = video.h3.text + u', ' + video.find(u'span', {u'id':u'videosearch_date'}).text
        description = video.find(u'span', {u'id':u'videosearch_caption'}).text
        
        infoLabels = {u'Title': title, u'Plot': description, u'PlotOutline': description}
        
        thumbnail = video.img[u'src']
        
        self.AddEpisodeItem(title, thumbnail, infoLabels, page, listItems)
    
#==============================================================================

    def ListSearchShows(self, html):
        logger.debug(u"")
        listItems = []

        soup = BeautifulSoup(html)
        videos = soup.findAll(u'li', u'unselected_video')

        for video in videos:
            try:
                self.AddEpisodeToSearchList(listItems, video)
            except (Exception) as exception:
                if not isinstance(exception, LoggingException):
                    exception = LoggingException.fromException(exception)
            
                # "Error processing search result"
                exception.addLogMessage(logMessage = "Error processing search result" + u"\n" + repr(video))
                exception.process("Error processing search result", u"", logging.WARNING)
            

#        xbmcplugin.addDirectoryItems( handle=self.pluginHandle, items=listItems )
#        xbmcplugin.endOfDirectory( handle=self.pluginHandle, succeeded=True )
        

#        return True
        return listItems

    def GetSWFPlayer(self, flowPlayerScript):
        logger.debug(u"")
        
        try:
            swfPlayer = utils.findString( u"TV3Provider::GetSWFPlayer()", u"flowplayer\(\"flowPlayer\",\s+{src:\s+\"(.+?)\"", flowPlayerScript)
#            swfPlayer = soup.find('div', {'id':'flowPlayer'}).object['data']
            if swfPlayer is None:
                swfPlayer = swfDefault

            return swfPlayer
        
        except (Exception) as exception:
            if not isinstance(exception, LoggingException):
                exception = LoggingException.fromException(exception)
            
            # Unable to determine swfPlayer URL. Using default: %s
            exception.addLogMessage("Unable to determine swfPlayer URL. Using default %s" % swfDefault)
            exception.process(severity = logging.WARNING)
            return swfDefault

#==============================================================================
    def GetEpisodeInfoCategory(self, gridshow):
        logger.debug(u"")

        """
        <div id="gridshow">
            <a title="3player | Snog Marry Avoid, 22/11/2012. Jenny meets blonde Danielle, gothic geisha Azelie and outrageous mother Jay" href="http://www.tv3.ie/3player/show/452/56083/1/Snog-Marry-Avoid">
                <img alt="3player | Snog Marry Avoid, 22/11/2012. Jenny meets blonde Danielle, gothic geisha Azelie and outrageous mother Jay" src="./3player   Home_files/snog_nov22_3player_1_56083_180x102.jpg" class="shadow smallroundcorner">
            </a>
            <h3>
                <a title="3player | Snog Marry Avoid, 22/11/2012. Jenny meets blonde Danielle, gothic geisha Azelie and outrageous mother Jay" href="http://www.tv3.ie/3player/show/452/56083/1/Snog-Marry-Avoid">Snog Marry Avoid</a>
            </h3>
            <span id="gridcaption">Jenny meets blonde Danielle, gothic geisha Azelie and out...</span>
            <span id="griddate">22/11/2012</span>
            <span id="gridduration">00:23:24</span>
        </div>
        """
        htmlparser = HTMLParser.HTMLParser()
        
        titleData = htmlparser.unescape(gridshow.a[u'title'])
        
        match=re.search(u"3player\s+\|\s+(.+),\s+(\d\d/\d\d/\d\d\d\d)\.\s*(.*)", titleData) 
        title=match.group(1) + u", " + match.group(2)
        description = match.group(3)

        infoLabels = {u'Title': title, u'Plot': description, u'PlotOutline': description}

        logger.debug(u"infoLabels: %s" % infoLabels)
        return infoLabels

#==============================================================================
    #TODO Add date
    def GetEpisodeInfo(self, soup):
        logger.debug("")

        htmlparser = HTMLParser.HTMLParser()
        
        infoLabels = { 'grabber' : 'irishtv',
                       'scraperName' : self.GetProviderId(),
                       'timestamp' : time() }

        meta = soup.findAll(u'meta')
        for item in meta:
            prop = item.get(u'property')
            if not prop:
                continue
            if prop in metaMap:
                infoLabels[metaMap[prop]] = htmlparser.unescape(item[u'content'])

        labels = soup.findAll(u'div', id="descLabel")
        for label in labels:
            text = label.string
            if not text in labelMap:
                continue
            detail = label.nextSibling
            value = detail.string
            infoLabels[labelMap[text]] = value

        if 'duration' in infoLabels:
            parts = infoLabels['duration'].split(":")
            duration = 0
            for part in parts:
                duration *= 60
                duration += int(part)
            infoLabels['duration'] = duration

        logger.debug(u"infoLabels: %s" % infoLabels)
        return infoLabels

#==============================================================================
    def InitialiseRTMP(self, soup):
        logger.debug(u"")

        try:
            flowPlayerScript = unicode(soup.find(u'div', {u'id':u'flowPlayer'}).findNextSibling(u'script').text)

            rtmpStr = utils.findString( u"TV3Provider::InitialiseRTMP()", u"netConnectionUrl: \"(.+?)\"", flowPlayerScript)
            rootIndex = rtmpStr[8:].index(u'/') + 9
            app = rtmpStr[rootIndex:]
            swfUrl = self.GetSWFPlayer(flowPlayerScript)
            playPath = utils.findString( u"TV3Provider::InitialiseRTMP()", u"playlist:\s+\[\s+{\s+url:\s+\"(.+?)\"", flowPlayerScript)
        
            rtmpVar = rtmp.RTMP(rtmp = rtmpStr, app = app, swfVfy = swfUrl, playPath = playPath)
            self.AddSocksToRTMP(rtmpVar)

            return rtmpVar
        except (Exception) as exception:
            if not isinstance(exception, LoggingException):
                exception = LoggingException.fromException(exception)

            # Error getting RTMP data
            exception.addLogMessage("Error getting RTMP data")
            raise exception
        
    def PlayEpisode(self, page, resumeFlag):
        logger.debug(u"")

        try:
            html = None
            logger.info(u"urlRoot: " + urlRoot + u", page: " + page )
            html = self.httpManager.GetWebPage( urlRoot + page, 1800 )
            #raise Exception("test1", "test2")
        except (Exception) as exception:
            if not isinstance(exception, LoggingException):
                exception = LoggingException.fromException(exception)

            if html is not None:
                msg = u"html:\n\n%s\n\n" % html
                exception.addLogMessage(msg)
                
            # Error getting web page
            exception.addLogMessage("Error getting web page")
            exception.process(severity = self.logLevel(logging.ERROR))
            return False

        soup = BeautifulSoup(html)

        ageCheck = soup.find(u'div', {u'id':u'age_check_form_row'})
        
        if ageCheck is not None:
            
#            if self.dialog.iscanceled():
#                return False
            # "Getting episode info"
            logger.info("Getting episode info")
#            self.dialog.update(25, self.language(30084))
            try:
                html = None
                html = self.httpManager.GetWebPage( urlRoot + page, 1800, values = {u'age_ok':'1'} )
                soup = BeautifulSoup(html)
            except (Exception) as exception:
                exception = LoggingException.fromException(exception)
    
                if html is not None:
                    msg = u"html:\n\n%s\n\n" % html
                    exception.addLogMessage(msg)
                    
                # Error getting web page: %s
                exception.addLogMessage("Error getting web page: " + ( urlRoot + page ) )
    
                # Error getting web page
                exception.process("Error getting web page", u'', severity = self.logLevel(logging.ERROR))
                return False
    
        rtmpVar = self.InitialiseRTMP(soup)

        infoLabels = self.GetEpisodeInfo(soup)
        thumbnail = soup.find(u'meta', {u'property' : u'og:image'})[u'content']
        defaultFilename = infoLabels[u'Title']

        resumeKey = unicode(zlib.crc32(page))
        infoLabels['id'] = resumeKey
        return self.PlayOrDownloadEpisode(infoLabels, thumbnail, rtmpVar, defaultFilename, url = None, subtitles = None, resumeKey = resumeKey, resumeFlag = resumeFlag)

#==============================================================================
    #TODO Handle exceptions?
    def DoSearchQuery( self, query ):
        logger.debug(u"query: %s" % query)
        
        values = {u'queryString':query, u'limit':20}
#        headers = {'DNT':'1', 'X-Requested-With':'XMLHttpRequest' }
        headers = {}
        headers[u'DNT'] = u'1'
        headers[u'Referer'] = u'http://www.tv3.ie/3player/'  
        headers[u'Content-Type'] = u'application/x-www-form-urlencoded; charset=UTF-8'
        
        html = self.httpManager.GetWebPage( searchUrl, 1800, values = values, headers = headers )
        if html is None or html == u'':
            # Data returned from web page: %s, is: '%s'
            logException = LoggingException(logMessage = "Data returned from web page: %s, is: '%s'" % ( searchUrl, html ))

            # Error getting web page
            logException.process("Error getting web page", u'', self.logLevel(logging.ERROR))
            return False

        # Fix fcuked up TV3 HTML formatting
        html = html.replace(u"<h3 id='search_heading'>Videos</h2>", "<h3 id='search_heading'>Videos</h3>")
        return self.ListSearchShows(html)

    def ListCalendar(self):
        logger.debug(u"")
        listItems = []

        try:
            html = None
            html = self.httpManager.GetWebPage(rootMenuUrl, 300)
            minDateString=re.search( u"minDate: '([0-9][0-9]/[0-9][0-9]/[0-9][0-9][0-9][0-9])'", html).group(1)
            maxDateString=re.search( u"maxDate: '([0-9][0-9]/[0-9][0-9]/[0-9][0-9][0-9][0-9])'", html).group(1)
    
            minDate = date.fromtimestamp(mktime(strptime(minDateString, u"%m/%d/%Y")))
            today = date.fromtimestamp(mktime(strptime(maxDateString, u"%m/%d/%Y")))
        
            # Today
            newLabel = u"Today"
            newListItem = { 'label' : newLabel }
#            newListItem = xbmcgui.ListItem( label=newLabel )
            url = self.GetURLStart() + u'&date=' + maxDateString
            listItems.append( (url,newListItem,True) )
        
            # Yesterday
            newLabel = u"Yesterday"
            newListItem = { 'label' : newLabel }
#            newListItem = xbmcgui.ListItem( label=newLabel )
            url = self.GetURLStart() + u'&date=' + (today - timedelta(1)).strftime(u"%m/%d/%Y")
            listItems.append( (url,newListItem,True) )
        
            # Weekday
            newLabel = (today - timedelta(2)).strftime(u"%A")
            newListItem = { 'label' : newLabel }
#            newListItem = xbmcgui.ListItem( label=newLabel )
            url = self.GetURLStart() + u'&date=' + (today - timedelta(2)).strftime(u"%m/%d/%Y")
            listItems.append( (url,newListItem,True) )
        
            # Weekday
            newLabel = (today - timedelta(3)).strftime(u"%A")
            newListItem = { 'label' : newLabel }
#            newListItem = xbmcgui.ListItem( label=newLabel )
            url = self.GetURLStart() + u'&date=' + (today - timedelta(3)).strftime(u"%m/%d/%Y")
            listItems.append( (url,newListItem,True) )
        
            currentDate = today - timedelta(4)
            sentinelDate = minDate - timedelta(1)
            while currentDate > sentinelDate:
                newLabel = currentDate.strftime(u"%A, %d %B %Y")
                newListItem = { 'label' : newLabel }
#                newListItem = xbmcgui.ListItem( label=newLabel )
                url = self.GetURLStart() + u'&date=' + currentDate.strftime(u"%m/%d/%Y")
                listItems.append( (url,newListItem,True) )
    
                currentDate = currentDate - timedelta(1) 
        
#            xbmcplugin.addDirectoryItems( handle=self.pluginHandle, items=listItems )
#            xbmcplugin.endOfDirectory( handle=self.pluginHandle, succeeded=True )
            
#            return True
            return listItems
        except (Exception) as exception:
            if not isinstance(exception, LoggingException):
                exception = LoggingException.fromException(exception)
            
            if html is not None:
                msg = u"html:\n\n%s\n\n" % html
                exception.addLogMessage(msg)
                
            # "Error creating calendar list"
            message = "Error creating calendar list"
            details = utils.valueIfDefined(minDateString, u'minDateString') + u", "
            details = details + utils.valueIfDefined(maxDateString, u'maxDateString') + u", "
            
            if utils.variableDefined( currentDate ):
                details = details + u"currentDate: " + unicode(currentDate) + u", "
            else:
                details = details + u"currentDate: Not defined"
                
            details = details + utils.valueIfDefined(url, u'url')
            
            exception.addLogMessage(logMessage = message + u"\n" + details)
            # "Error creating calendar list"
            exception.process(message, u"", self.logLevel(logging.ERROR))
            return False
    
    def ListByDate(self, date):
        values = {u'queryString' : date}
        
        html = None
        html = self.httpManager.GetWebPage( calendarUrl, 3600, values = values)
        if html is None or html == u'':
            # Data returned from web page: %s, is: '%s'
            logException = LoggingException(logMessage = "Data returned from web page: %s, is '%s'" % ( searchUrl, html ))

            # Error getting web page
            logException.process("Error getting web page", u'', self.logLevel(logging.ERROR))
            return False

        soup = BeautifulSoup(html)

        listItems = []
        htmlparser = HTMLParser.HTMLParser()
        videos = soup.findAll(u'div', {u'id':u'tooltip_showvideo_cal'})
        
        if len(videos) == 1 and len(videos[0].findAll(u'a')) == 0:
            # No videos broadcast on this date.
#            xbmc.executebuiltin(u'XBMC.Notification(IrishTV, %s)' % (videos[0].text))
            return True
        
        for video in videos:
            try:
                anchors = video.findAll(u'a')
                
                time = anchors[2].small.text
                title = self.fullDecode( anchors[1].b.text + u", " + time )
                description = self.fullDecode( anchors[3].text )
                infoLabels = {u'Title': title, u'Plot': description, u'PlotOutline': description}
    
                page = anchors[0][u'href']
                thumbnail = anchors[0].img[u'src']
                
                self.AddEpisodeItem(title, thumbnail, infoLabels, page, listItems)
            except (Exception) as exception:
                if not isinstance(exception, LoggingException):
                    exception = LoggingException.fromException(exception)
                
                if video is not None:
                    msg = u"video:\n\n%s\n\n" % video
                    exception.addLogMessage(msg)
                    
                # "Error processing video"
                exception.addLogMessage(logMessage = "Error processing video\n" + repr(video))
                # "Error processing video"
                exception.process("Error processing %s video" % programme, u"", logging.WARNING)
                continue
            
#        xbmcplugin.addDirectoryItems( handle=self.pluginHandle, items=listItems )
#        xbmcplugin.endOfDirectory( handle=self.pluginHandle, succeeded=True )
            
#        return True
        return listItems


