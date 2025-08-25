// Background service worker

// Constants
const CONFIG = {
  SERVER_URL: 'http://localhost:8080',
  HISTORY_SEARCH_DAYS: 30,
  MAX_HISTORY_RESULTS: 3000,
  MAX_SUGGESTED_RESULTS: 10000,
  MAX_RETRY_CANDIDATES: 4,
  MIN_MATCH_SCORE: 0.3,
  SUGGESTED_MIN_VISITS: 3,
  MAX_SUGGESTIONS: 20,
  RETRY_DELAY_MS: 1000
};

const VIDEO_SITE_REGEX = /youtube|vimeo|dailymotion|twitch|pornhub|xvideos|redtube|xnxx|xhamster|spankbang|tnaflix|tube8|youporn|pornmd|4tube|sunporno|nuvid|eporner|gotporn|vjav|porntrex|heavy-r|motherless|hqporner|fapbase|rule34video|redgifs|reallifecam|adulttime|brazzers|bangbros|reality/i;

const VIDEO_EXTENSIONS = /(mp4|mkv|avi|mov|webm|flv|wmv|m4v|3gp|mpg|mpeg|ts|m2ts|vob|ogv|rm|rmvb|asf|divx|xvid|f4v)/i;

const BADGE_COLORS = {
  VIDEO_DETECTED: '#4CAF50',
  DEFAULT: ''
};

const TITLES = {
  VIDEO_DOWNLOAD: 'Download video from this page',
  NO_VIDEO: 'Quikvid-DL - No video detected'
};

chrome.runtime.onInstalled.addListener(() => {
  console.log('Quikvid-DL Extension installed');
});

// Handle messages from content scripts and web interface
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'retryFromWebInterface') {
    // Handle retry request from web interface
    handleWebInterfaceRetry(message.filename, sendResponse);
    return true; // Keep the message channel open for async response
  } else if (message.action === 'scanSuggestedDownloads') {
    // Handle suggested downloads scan request
    handleSuggestedDownloadsScan(message.days || 7, sendResponse);
    return true; // Keep the message channel open for async response
  } else if (message.action === 'pageVideoInfo') {
    // Update badge based on video detection
    const isVideoPage = message.data.isVideoSite || 
                       message.data.hasVideoElements || 
                       message.data.hasVideoKeywords;
    
    if (sender.tab) {
      updateBadgeForVideoDetection(sender.tab.id, isVideoPage);
    }
  }
});

// Helper function to update badge based on video detection
function updateBadgeForVideoDetection(tabId, isVideoPage) {
  if (isVideoPage) {
    chrome.action.setBadgeText({
      text: '📹',
      tabId: tabId
    });
    chrome.action.setBadgeBackgroundColor({
      color: BADGE_COLORS.VIDEO_DETECTED,
      tabId: tabId
    });
    chrome.action.setTitle({
      title: TITLES.VIDEO_DOWNLOAD,
      tabId: tabId
    });
  } else {
    clearBadge(tabId);
  }
}

// Helper function to clear badge
function clearBadge(tabId) {
  chrome.action.setBadgeText({
    text: BADGE_COLORS.DEFAULT,
    tabId: tabId
  });
  chrome.action.setTitle({
    title: TITLES.NO_VIDEO,
    tabId: tabId
  });
}

// Helper function to clean filename for search
function cleanFilenameForSearch(filename) {
  return filename
    .replace(new RegExp(`\\.(${VIDEO_EXTENSIONS.source})(\\.(part|tmp|crdownload))*$`, 'i'), '')
    .replace(/[_-]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

// Helper function to search browser history
async function searchBrowserHistory(maxResults, startTime) {
  return new Promise((resolve) => {
    chrome.history.search({
      text: '',
      maxResults: maxResults,
      startTime: startTime
    }, (results) => {
      resolve(results || []);
    });
  });
}

// Helper function to check if URL is a video site
function isVideoSite(url) {
  return VIDEO_SITE_REGEX.test(url);
}

// Helper function to delay execution
function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// Clear badge when tab changes
chrome.tabs.onActivated.addListener((activeInfo) => {
  clearBadge(activeInfo.tabId);
});

// Handle extension icon click (when popup is disabled)
chrome.action.onClicked.addListener((tab) => {
  // This only fires if popup is not set, but we have popup.html
  console.log('Extension clicked for tab:', tab.url);
});

// Handle retry requests from web interface
async function handleWebInterfaceRetry(filename, sendResponse) {
  try {
    console.log(`Searching browser history for retry: ${filename}`);
    
    // Clean the filename to extract search terms
    const searchTitle = cleanFilenameForSearch(filename);
    
    // Search browser history
    const startTime = Date.now() - (CONFIG.HISTORY_SEARCH_DAYS * 24 * 60 * 60 * 1000);
    const historyItems = await searchBrowserHistory(CONFIG.MAX_HISTORY_RESULTS, startTime);
    
    console.log(`Found ${historyItems.length} history items to search`);
    
    // Score and find best matches
    const matches = findMatchingVideoUrls(historyItems, searchTitle);
    
    console.log(`Found ${matches.length} potential matches`);
    
    // Try downloading from the best matches
    const result = await tryDownloadFromCandidates(matches, searchTitle);
    sendResponse(result);
    
  } catch (error) {
    console.error('Error in handleWebInterfaceRetry:', error);
    sendResponse({
      success: false,
      error: `Browser history search failed: ${error.message}`
    });
  }
}

// Helper function to find matching video URLs from history
function findMatchingVideoUrls(historyItems, searchTitle) {
  const matches = [];
  
  for (const item of historyItems) {
    if (!item.url || !item.title) continue;
    
    if (isVideoSite(item.url)) {
      const titleScore = calculateFuzzyMatch(searchTitle.toLowerCase(), item.title.toLowerCase());
      const urlScore = calculateFuzzyMatch(searchTitle.toLowerCase(), item.url.toLowerCase());
      const finalScore = Math.max(titleScore, urlScore);
      
      if (finalScore >= CONFIG.MIN_MATCH_SCORE) {
        matches.push({
          url: item.url,
          title: item.title,
          score: finalScore,
          visitCount: item.visitCount || 1
        });
      }
    }
  }
  
  // Sort by score and visit count
  matches.sort((a, b) => {
    if (Math.abs(a.score - b.score) < 0.1) {
      return b.visitCount - a.visitCount;
    }
    return b.score - a.score;
  });
  
  return matches;
}

// Helper function to try downloading from candidates
async function tryDownloadFromCandidates(matches, searchTitle) {
  const candidatesToTry = matches.slice(0, CONFIG.MAX_RETRY_CANDIDATES);
  let lastError = null;
  
  for (let i = 0; i < candidatesToTry.length; i++) {
    const candidate = candidatesToTry[i];
    
    if (candidate.score < CONFIG.MIN_MATCH_SCORE) break;
    
    console.log(`Trying candidate ${i + 1}/${candidatesToTry.length}: ${candidate.url} (${(candidate.score * 100).toFixed(1)}% match)`);
    
    try {
      const response = await fetch(`${CONFIG.SERVER_URL}/download`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: candidate.url,
          title: searchTitle,
          openFolder: true,
          isRetry: true
        })
      });
      
      if (response.ok) {
        const result = await response.json();
        return {
          success: true,
          message: `Found URL with ${(candidate.score * 100).toFixed(1)}% match (attempt ${i + 1}). Retry started!`,
          downloadId: result.downloadId,
          matchedUrl: candidate.url,
          attemptNumber: i + 1
        };
      } else {
        const errorText = await response.text();
        lastError = `Server error: ${response.status} - ${errorText}`;
        console.log(`Attempt ${i + 1} failed: ${lastError}`);
      }
    } catch (downloadError) {
      lastError = downloadError.message;
      console.log(`Attempt ${i + 1} failed: ${lastError}`);
    }
    
    // Delay before next attempt
    if (i < candidatesToTry.length - 1) {
      await delay(CONFIG.RETRY_DELAY_MS);
    }
  }
  
  return {
    success: false,
    error: `Tried ${candidatesToTry.length} URL(s) but all failed. Last error: ${lastError}`,
    foundMatches: candidatesToTry.map(m => ({ url: m.url, title: m.title, score: m.score }))
  };
}

// Fuzzy matching algorithm
function calculateFuzzyMatch(str1, str2) {
  if (!str1 || !str2) return 0;
  
  const s1 = str1.toLowerCase().replace(/[^\w\s]/g, '').trim();
  const s2 = str2.toLowerCase().replace(/[^\w\s]/g, '').trim();
  
  if (s1 === s2) return 1;
  
  const words1 = s1.split(/\s+/).filter(w => w.length > 2);
  const words2 = s2.split(/\s+/).filter(w => w.length > 2);
  
  if (words1.length === 0 || words2.length === 0) return 0;
  
  let matchedWords = 0;
  let totalImportance = 0;
  
  for (const word1 of words1) {
    const importance = word1.length > 4 ? 2 : 1;
    totalImportance += importance;
    
    for (const word2 of words2) {
      if (word1.includes(word2) || word2.includes(word1) || 
          (word1.length > 3 && word2.length > 3 && 
           (word1.substring(0, 4) === word2.substring(0, 4)))) {
        matchedWords += importance;
        break;
      }
    }
  }
  
  return totalImportance > 0 ? matchedWords / totalImportance : 0;
}

// Handle suggested downloads scan
async function handleSuggestedDownloadsScan(days, sendResponse) {
  try {
    console.log(`Scanning browser history for suggested downloads (${days} days)`);
    
    // Search browser history for the specified time period
    const historyItems = await new Promise((resolve) => {
      chrome.history.search({
        text: '',
        maxResults: 10000,
        startTime: Date.now() - (days * 24 * 60 * 60 * 1000)
      }, (results) => {
        resolve(results || []);
      });
    });
    
    console.log(`Found ${historyItems.length} history items to analyze`);
    
    // Group by URL and count visits
    const urlVisitCounts = {};
    for (const item of historyItems) {
      if (!item.url || !item.title) continue;
      
      // Check if it's a video site
      const isVideoSite = /youtube|vimeo|dailymotion|twitch|pornhub|xvideos|redtube|xnxx|xhamster|spankbang|tnaflix|tube8|youporn|pornmd|4tube|sunporno|nuvid|eporner|gotporn|vjav|porntrex|heavy-r|motherless|hqporner|fapbase|rule34video|redgifs|reallifecam|adulttime|brazzers|bangbros|reality/i.test(item.url);
      
      if (isVideoSite) {
        if (!urlVisitCounts[item.url]) {
          urlVisitCounts[item.url] = {
            url: item.url,
            title: item.title,
            visitCount: 0,
            lastVisitTime: item.lastVisitTime
          };
        }
        urlVisitCounts[item.url].visitCount += item.visitCount || 1;
        
        // Keep the most recent title
        if (item.lastVisitTime > urlVisitCounts[item.url].lastVisitTime) {
          urlVisitCounts[item.url].title = item.title;
          urlVisitCounts[item.url].lastVisitTime = item.lastVisitTime;
        }
      }
    }
    
    // Filter for URLs visited 3+ times and sort by visit count
    const suggestions = Object.values(urlVisitCounts)
      .filter(item => item.visitCount >= 3)
      .sort((a, b) => {
        if (b.visitCount !== a.visitCount) {
          return b.visitCount - a.visitCount;
        }
        return b.lastVisitTime - a.lastVisitTime;
      })
      .slice(0, 20); // Limit to top 20 suggestions
    
    console.log(`Found ${suggestions.length} suggested downloads`);
    
    sendResponse({
      success: true,
      suggestions: suggestions
    });
    
  } catch (error) {
    console.error('Error in handleSuggestedDownloadsScan:', error);
    sendResponse({
      success: false,
      error: `Failed to scan browser history: ${error.message}`
    });
  }
}