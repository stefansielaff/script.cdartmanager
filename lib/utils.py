# -*- coding: utf-8 -*-
import datetime
import errno
import htmlentitydefs
import os
import re
import traceback
import urllib

import xbmc
import xbmcgui
import xbmcvfs

import cdam
from file_item import Thumbnails

__cdam__ = cdam.CDAM()
__settings__ = cdam.Settings()
__language__ = __cdam__.getLocalizedString

dialog = xbmcgui.DialogProgress()


def change_characters(text):
    original = list(text)
    final = []
    if __settings__.enable_replace_illegal():
        replace_character = __settings__.replace_character()
        for i in original:
            if i in __settings__.illegal_characters():
                final.append(replace_character)
            else:
                final.append(i)
        temp = "".join(final)
        if temp.endswith(".") and __settings__.change_period_atend():
            text = temp[:len(temp) - 1] + replace_character
        else:
            text = temp
    return text


def smart_unicode(s):
    """credit : sfaxman"""
    if not s:
        return ''
    try:
        if not isinstance(s, basestring):
            if hasattr(s, '__unicode__'):
                s = unicode(s)
            else:
                s = unicode(str(s), 'UTF-8')
        elif not isinstance(s, unicode):
            s = unicode(s, 'UTF-8')
    except Exception as e:
        log(e.message, xbmc.LOGDEBUG)
        if not isinstance(s, basestring):
            if hasattr(s, '__unicode__'):
                s = unicode(s)
            else:
                s = unicode(str(s), 'ISO-8859-1')
        elif not isinstance(s, unicode):
            s = unicode(s, 'ISO-8859-1')
    return s


def smart_utf8(s):
    return smart_unicode(s).encode('utf-8')


def get_unicode(to_decode):
    final = []
    try:
        return to_decode.encode('utf8')
    except UnicodeError:
        while True:
            try:
                final.append(to_decode.decode('utf8'))
                break
            except UnicodeDecodeError as exc:
                # everything up to crazy character should be good
                final.append(to_decode[:exc.start].decode('utf8'))
                # crazy character is probably latin1
                final.append(to_decode[exc.start].decode('latin1'))
                # remove already encoded stuff
                to_decode = to_decode[exc.start + 1:]
        return "".join(final)


def settings_to_log(settings_path):
    try:
        log("Settings\n", xbmc.LOGDEBUG)
        # open path
        settings_file = open(settings_path, "r")
        settings_file_read = settings_file.read()
        settings_list = settings_file_read.replace("<settings>\n", "").replace("</settings>\n", "").split("/>\n")
        # close socket
        settings_file.close()
        for setting in settings_list:
            match = re.search('    <setting id="(.*?)" value="(.*?)"', setting)
            if not match:
                match = re.search("""    <setting id="(.*?)" value='(.*?)'""", setting)
            if match:
                log("%30s: %s" % (match.group(1), str(unescape(match.group(2).decode('utf-8', 'ignore')))),
                    xbmc.LOGDEBUG)
    except Exception as e:
        log(e.message, xbmc.LOGERROR)
        traceback.print_exc()


def clear_image_cache(url):
    thumb = Thumbnails().get_cached_picture_thumb(url)
    png = os.path.splitext(thumb)[0] + ".png"
    dds = os.path.splitext(thumb)[0] + ".dds"
    jpg = os.path.splitext(thumb)[0] + ".jpg"
    if xbmcvfs.exists(thumb):
        xbmcvfs.delete(thumb)
    if xbmcvfs.exists(png):
        xbmcvfs.delete(png)
    if xbmcvfs.exists(jpg):
        xbmcvfs.delete(jpg)
    if xbmcvfs.exists(dds):
        xbmcvfs.delete(dds)


def empty_tempxml_folder():
    # Helix: paths MUST end with trailing slash
    tempxml_folder = __cdam__.path_temp_xml()
    if xbmcvfs.exists(os.path.join(tempxml_folder, '')):
        for file_name in os.listdir(os.path.join(tempxml_folder, '')):
            xbmcvfs.delete(os.path.join(tempxml_folder, file_name))
    else:
        pass


def get_html_source(url, path, save_file=True, overwrite=False):
    """ fetch the html source """
    log("Retrieving HTML Source", xbmc.LOGDEBUG)
    log("Fetching URL: %s" % url, xbmc.LOGDEBUG)
    error = False
    htmlsource = "null"
    file_name = ""
    if save_file:
        path += ".json"
        tempxml_folder = __cdam__.path_temp_xml()
        if not xbmcvfs.exists(os.path.join(tempxml_folder, '')):
            xbmcvfs.mkdir(os.path.join(tempxml_folder, ''))
        file_name = os.path.join(tempxml_folder, path)

    class AppURLopener(urllib.FancyURLopener):
        version = __cdam__.user_agent()

    urllib._urlopener = AppURLopener()
    for i in range(0, 4):
        try:
            if save_file:
                if xbmcvfs.exists(file_name):
                    file_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(file_name))
                    file_age = datetime.datetime.today() - file_mtime
                    if file_age.days > 14:  # yes i know... but this is temporary and will be configurable in a later release
                        log("Cached file is %s days old, refreshing" % file_age.days, xbmc.LOGNOTICE)
                        xbmcvfs.delete(file_name)

                if xbmcvfs.exists(file_name) and not overwrite:
                    log("Retrieving local source", xbmc.LOGDEBUG)
                    sock = open(file_name, "r")
                else:
                    log("Retrieving online source", xbmc.LOGDEBUG)
                    urllib.urlcleanup()
                    sock = urllib.urlopen(url)
            else:
                urllib.urlcleanup()
                sock = urllib.urlopen(url)
            htmlsource = sock.read()
            if save_file and htmlsource not in ("null", ""):
                if not xbmcvfs.exists(file_name) or overwrite:
                    file(file_name, "w").write(htmlsource)
            sock.close()
            break
        except IOError as e:
            log("error: %s" % e, xbmc.LOGERROR)
            log("e.errno: %s" % e.errno, xbmc.LOGERROR)
            if not e.errno == "socket error":
                log("errno.errorcode: %s" % errno.errorcode[e.errno], xbmc.LOGERROR)
        except Exception as e:
            log("error: %s" % e, xbmc.LOGERROR)
            traceback.print_exc()
            log("!!Unable to open page %s" % url, xbmc.LOGDEBUG)
            error = True
    if error:
        return "null"
    else:
        log("HTML Source:\n%s" % htmlsource, xbmc.LOGDEBUG)
        if htmlsource == "":
            htmlsource = "null"
        return htmlsource


def unescape(text):
    def fixup(m):
        text_ = m.group(0)
        if text_[:2] == "&#":
            # character reference
            try:
                if text_[:3] == "&#x":
                    return unichr(int(text_[3:-1], 16))
                else:
                    return unichr(int(text_[2:-1]))
            except ValueError:
                pass
        else:
            # named entity
            try:
                text_ = unichr(htmlentitydefs.name2codepoint[text_[1:-1]])
            except KeyError:
                pass
        return text_  # leave as is

    return re.sub("&#?\w+;", fixup, text)


# centralized Dialog function from Artwork Downloader
# Define dialogs
def dialog_msg(action,
               percent=0,
               heading='',
               line1='',
               line2='',
               line3='',
               background=False,
               nolabel=__language__(32179),
               yeslabel=__language__(32178)):
    # Fix possible unicode errors 
    heading = heading.encode('utf-8', 'ignore')
    line1 = line1.encode('utf-8', 'ignore')
    line2 = line2.encode('utf-8', 'ignore')
    line3 = line3.encode('utf-8', 'ignore')
    # Dialog logic
    if not heading == '':
        heading = __cdam__.name() + " - " + heading
    else:
        heading = __cdam__.name()
    if not line1:
        line1 = ""
    if not line2:
        line2 = ""
    if not line3:
        line3 = ""
    if not background:
        if action == 'create':
            dialog.create(heading, line1, line2, line3)
        if action == 'update':
            dialog.update(percent, line1, line2, line3)
        if action == 'close':
            dialog.close()
        if action == 'iscanceled':
            if dialog.iscanceled():
                return True
            else:
                return False
        if action == 'okdialog':
            xbmcgui.Dialog().ok(heading, line1, line2, line3)
        if action == 'yesno':
            return xbmcgui.Dialog().yesno(heading, line1, line2, line3, nolabel, yeslabel)
    if background:
        if action == 'create' or action == 'okdialog':
            if line2 == '':
                msg = line1
            else:
                msg = line1 + ': ' + line2
            if __settings__.notify_in_background():
                xbmc.executebuiltin("XBMC.Notification(%s, %s, 7500, %s)" % (heading, msg, __cdam__.file_icon()))


def log(text, severity=xbmc.LOGDEBUG):
    if type(text).__name__ == 'unicode':
        text = text.encode('utf-8')
    message = ('[%s] - %s' % (__cdam__.name(), text.__str__()))
    xbmc.log(msg=message, level=severity)