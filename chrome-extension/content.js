// Content script - runs on all web pages
(function() {
  'use strict';

  // Function to detect if current page is likely a video page
  function detectVideoPage() {
    const url = window.location.href;
    const hostname = window.location.hostname;
    
    // List of supported video sites (matching yt-dlp support)
    const videoSites = [
      'youtube.com', 'youtu.be', 'tiktok.com', 'instagram.com',
      'facebook.com', 'twitter.com', 'x.com', 'twitch.tv',
      'vimeo.com', 'dailymotion.com', 'soundcloud.com',
      'reddit.com', '9gag.com', 'bilibili.com', 'pinterest.com',
      'porntrex.com', 'eporner.com', 'xhamster.com', 'pornhub.com'
    ];
    
    // Check if current site is in supported list
    const isVideoSite = videoSites.some(site => 
      hostname.includes(site) || hostname.endsWith(site)
    );
    
    // Additional detection for video elements
    const hasVideoElements = document.querySelector('video') !== null;
    const hasVideoKeywords = /video|watch|clip|stream/i.test(url);
    
    return {
      isVideoSite,
      hasVideoElements,
      hasVideoKeywords,
      url: url,
      hostname: hostname,
      title: document.title
    };
  }
  
  // Function to extract specific video information
  function extractVideoInfo() {
    const info = detectVideoPage();
    
    // YouTube specific extraction
    if (info.hostname.includes('youtube.com') || info.hostname.includes('youtu.be')) {
      const videoId = extractYouTubeVideoId(info.url);
      if (videoId) {
        info.videoId = videoId;
        info.videoTitle = document.querySelector('h1.ytd-video-primary-info-renderer')?.textContent ||
                         document.querySelector('meta[name="title"]')?.content ||
                         info.title;
      }
    }
    
    // TikTok specific extraction
    if (info.hostname.includes('tiktok.com')) {
      info.videoTitle = document.querySelector('h1[data-e2e="browse-video-desc"]')?.textContent ||
                       document.querySelector('title')?.textContent ||
                       info.title;
    }
    
    // Instagram specific extraction
    if (info.hostname.includes('instagram.com')) {
      info.videoTitle = document.querySelector('h1')?.textContent ||
                       document.querySelector('meta[property="og:title"]')?.content ||
                       info.title;
    }
    
    return info;
  }
  
  function extractYouTubeVideoId(url) {
    const patterns = [
      /(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&\n?#]+)/,
      /youtube\.com\/embed\/([^&\n?#]+)/,
      /youtube\.com\/v\/([^&\n?#]+)/
    ];
    
    for (const pattern of patterns) {
      const match = url.match(pattern);
      if (match) return match[1];
    }
    return null;
  }
  
  // Listen for messages from popup
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'getVideoInfo') {
      const videoInfo = extractVideoInfo();
      sendResponse(videoInfo);
    }
    return true; // Keep message channel open for async response
  });
  
  // Send page info to background script when page loads
  setTimeout(() => {
    const videoInfo = extractVideoInfo();
    chrome.runtime.sendMessage({
      action: 'pageVideoInfo',
      data: videoInfo
    }).catch(() => {
      // Ignore errors if extension context is invalidated
    });
  }, 1000);
  
})();