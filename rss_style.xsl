<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="3.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                xmlns:atom="http://www.w3.org/2005/Atom" xmlns:dc="http://purl.org/dc/elements/1.1/"
                xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <xsl:output method="html" version="1.0" encoding="UTF-8" indent="yes"/>
  <xsl:template match="/">
    <html xmlns="http://www.w3.org/1999/xhtml">
      <head>
        <title><xsl:value-of select="/rss/channel/title"/> - RSS Feed</title>
        <meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1"/>
        <style type="text/css">
          body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background: #f6f8fa; color: #24292e; }
          .header { background: #fff; padding: 20px; border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 20px; text-align: center; }
          .header img { max-width: 200px; border-radius: 6px; margin-bottom: 10px; }
          h1 { margin: 0 0 10px 0; font-size: 24px; }
          p.desc { color: #586069; font-size: 16px; line-height: 1.5; }
          .episode { background: #fff; padding: 20px; border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 15px; }
          .episode h2 { margin: 0 0 10px 0; font-size: 18px; }
          .episode h2 a { color: #0366d6; text-decoration: none; }
          .episode h2 a:hover { text-decoration: underline; }
          .meta { color: #586069; font-size: 12px; margin-bottom: 10px; }
          audio { width: 100%; margin-top: 10px; }
        </style>
      </head>
      <body>
        <div class="header">
          <xsl:if test="/rss/channel/image/url">
            <img src="{/rss/channel/image/url}" alt="Podcast Cover"/>
          </xsl:if>
          <h1><xsl:value-of select="/rss/channel/title"/></h1>
          <p class="desc"><xsl:value-of select="/rss/channel/description"/></p>
          <p>
            <a href="{/rss/channel/link}">Visit Website</a>
          </p>
        </div>

        <xsl:for-each select="/rss/channel/item">
          <xsl:sort select="title" order="descending"/>
          <div class="episode">
            <h2><a href="{link}"><xsl:value-of select="title"/></a></h2>
            <div class="meta">
              Published: <xsl:value-of select="pubDate"/>
            </div>
            <p><xsl:value-of select="description"/></p>
            <xsl:if test="enclosure">
              <audio controls="controls" preload="none">
                <source src="{enclosure/@url}" type="{enclosure/@type}"/>
                Your browser does not support the audio element.
              </audio>
            </xsl:if>
          </div>
        </xsl:for-each>
      </body>
    </html>
  </xsl:template>
</xsl:stylesheet>
