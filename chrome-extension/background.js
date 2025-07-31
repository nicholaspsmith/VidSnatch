// Background service worker
chrome.runtime.onInstalled.addListener(() => {
  console.log('Quikvid-DL Extension installed');
});

// Handle messages from content scripts
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'pageVideoInfo') {
    // Update badge based on video detection
    const isVideoPage = message.data.isVideoSite || 
                       message.data.hasVideoElements || 
                       message.data.hasVideoKeywords;
    
    if (isVideoPage && sender.tab) {
      chrome.action.setBadgeText({
        text: '📹',
        tabId: sender.tab.id
      });
      chrome.action.setBadgeBackgroundColor({
        color: '#4CAF50',
        tabId: sender.tab.id
      });
      chrome.action.setTitle({
        title: 'Download video from this page',
        tabId: sender.tab.id
      });
    } else if (sender.tab) {
      chrome.action.setBadgeText({
        text: '',
        tabId: sender.tab.id
      });
      chrome.action.setTitle({
        title: 'Quikvid-DL - No video detected',
        tabId: sender.tab.id
      });
    }
  }
});

// Clear badge when tab changes
chrome.tabs.onActivated.addListener((activeInfo) => {
  chrome.action.setBadgeText({
    text: '',
    tabId: activeInfo.tabId
  });
});

// Handle extension icon click (when popup is disabled)
chrome.action.onClicked.addListener((tab) => {
  // This only fires if popup is not set, but we have popup.html
  console.log('Extension clicked for tab:', tab.url);
});