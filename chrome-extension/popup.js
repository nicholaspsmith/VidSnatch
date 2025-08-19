// Multi-download popup JavaScript with progress tracking
document.addEventListener('DOMContentLoaded', async function() {
  const downloadBtn = document.getElementById('downloadBtn');
  const settingsBtn = document.getElementById('settingsBtn');
  const statusDiv = document.getElementById('status');
  const currentUrlDiv = document.getElementById('currentUrl');
  const downloadsContainer = document.getElementById('downloadsContainer');
  const downloadsEmpty = document.getElementById('downloadsEmpty');
  const downloadsSection = document.querySelector('.downloads-section');
  const openFolderToggle = document.getElementById('openFolderToggle');
  const folderPath = document.getElementById('folderPath');
  const openFolderBtn = document.getElementById('openFolderBtn');
  const serverStatus = document.getElementById('serverStatus');
  const serverStatusText = document.getElementById('serverStatusText');
  const stopServerBtn = document.getElementById('stopServerBtn');
  
  let currentVideoInfo = null;
  let activeDownloads = new Map(); // downloadId -> download object
  let progressInterval = null;
  let openFolderEnabled = true;
  let folderSelectionInProgress = false;
  let serverOnline = false;
  
  // Load settings and check for active downloads
  await loadSettings();
  await checkServerStatus();
  await loadCurrentFolderPath();
  await checkForActiveDownloads();
  
  // Get current tab and video info
  async function getCurrentTabInfo() {
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      
      // Send message to content script to get video info
      const videoInfo = await chrome.tabs.sendMessage(tab.id, { action: 'getVideoInfo' });
      
      currentVideoInfo = videoInfo;
      updateUI(videoInfo);
      
    } catch (error) {
      console.error('Error getting tab info:', error);
      showStatus('Error: Cannot access this page', 'error');
      currentUrlDiv.textContent = 'Cannot access current page';
      downloadBtn.disabled = true;
    }
  }
  
  async function loadSettings() {
    try {
      const result = await chrome.storage.local.get(['openFolderEnabled']);
      openFolderEnabled = result.openFolderEnabled !== false; // Default to true
      updateToggleUI();
    } catch (error) {
      console.error('Error loading settings:', error);
    }
  }
  
  async function loadCurrentFolderPath() {
    try {
      const response = await fetch('http://localhost:8080/current-folder');
      if (response.ok) {
        const data = await response.json();
        updateFolderPathDisplay(data.path);
      } else {
        folderPath.textContent = 'Unable to load folder path';
      }
    } catch (error) {
      console.error('Error loading folder path:', error);
      folderPath.textContent = 'Server not running';
    }
  }
  
  function updateFolderPathDisplay(path) {
    if (path) {
      // Show shortened path for better display
      const maxLen = 40;
      let displayPath = path;
      
      if (displayPath.length > maxLen) {
        // Show beginning and end of path
        const start = displayPath.substring(0, 15);
        const end = displayPath.substring(displayPath.length - 20);
        displayPath = `${start}...${end}`;
      }
      
      folderPath.textContent = displayPath;
      folderPath.title = `Click to change download folder\nCurrent: ${path}`;
    } else {
      folderPath.textContent = 'No folder set';
      folderPath.title = 'Click to set download folder';
    }
  }
  
  async function saveSettings() {
    try {
      await chrome.storage.local.set({ openFolderEnabled });
    } catch (error) {
      console.error('Error saving settings:', error);
    }
  }
  
  async function checkServerStatus() {
    try {
      const response = await fetch('http://localhost:8080/status', {
        method: 'GET',
        timeout: 3000
      });
      
      if (response.ok) {
        serverOnline = true;
        updateServerStatus(true);
      } else {
        serverOnline = false;
        updateServerStatus(false);
      }
    } catch (error) {
      serverOnline = false;
      updateServerStatus(false);
    }
  }
  
  function updateServerStatus(online) {
    serverOnline = online;
    
    if (online) {
      serverStatus.className = 'server-status online';
      serverStatusText.textContent = 'Server running on port 8080';
      stopServerBtn.disabled = false;
      downloadBtn.disabled = !currentVideoInfo || !(currentVideoInfo.isVideoSite || currentVideoInfo.hasVideoElements || currentVideoInfo.hasVideoKeywords);
    } else {
      serverStatus.className = 'server-status offline';
      serverStatusText.textContent = 'Server not running - run: ./start';
      stopServerBtn.disabled = true;
      downloadBtn.disabled = true;
    }
  }
  
  
  async function stopServer() {
    try {
      stopServerBtn.disabled = true;
      serverStatusText.textContent = 'Stopping server...';
      showStatus('Stopping Quikvid-DL server...', 'info');
      
      const response = await fetch('http://localhost:8080/stop-server', {
        method: 'POST'
      });
      
      if (response.ok) {
        showStatus('✅ Server stopped successfully!', 'success');
        updateServerStatus(false);
      } else {
        throw new Error('Failed to stop server');
      }
    } catch (error) {
      console.error('Error stopping server:', error);
      showStatus('❌ Failed to stop server. Please stop manually.', 'error');
      stopServerBtn.disabled = false;
    }
  }
  
  async function saveActiveDownloads() {
    try {
      const downloadsArray = Array.from(activeDownloads.entries()).map(([id, download]) => ({
        downloadId: id,
        videoInfo: download.videoInfo,
        timestamp: download.timestamp
      }));
      console.log('Saving active downloads:', downloadsArray);
      await chrome.storage.local.set({ activeDownloads: downloadsArray });
    } catch (error) {
      console.error('Error saving active downloads:', error);
    }
  }
  
  async function loadActiveDownloads() {
    try {
      const result = await chrome.storage.local.get(['activeDownloads']);
      const downloadsArray = result.activeDownloads || [];
      console.log('Loaded active downloads:', downloadsArray);
      
      activeDownloads.clear();
      downloadsArray.forEach(download => {
        activeDownloads.set(download.downloadId, {
          downloadId: download.downloadId,
          videoInfo: download.videoInfo,
          timestamp: download.timestamp
        });
      });
    } catch (error) {
      console.error('Error loading active downloads:', error);
    }
  }
  
  // Helper function to clean video titles
  function cleanVideoTitle(title) {
    if (!title) return title;
    
    // Remove "NA - " prefix (case-insensitive)
    if (title.toLowerCase().startsWith('na - ')) {
      title = title.substring(5);
    }
    
    // Remove other common unwanted prefixes
    const prefixesToRemove = [
      'undefined - ',
      'null - ',
      '[object Object] - ',
      'untitled - '
    ];
    
    const titleLower = title.toLowerCase();
    for (const prefix of prefixesToRemove) {
      if (titleLower.startsWith(prefix.toLowerCase())) {
        title = title.substring(prefix.length);
        break;
      }
    }
    
    // Clean up whitespace
    title = title.trim();
    
    // Return default if empty
    return title || 'Unknown Video';
  }

  function createDownloadElement(downloadId, videoInfo) {
    const downloadItem = document.createElement('div');
    downloadItem.className = 'download-item';
    downloadItem.id = `download-${downloadId}`;
    
    const rawTitle = videoInfo.videoTitle || videoInfo.title || 'Unknown Video';
    const title = cleanVideoTitle(rawTitle);
    
    // Check if this is the current page video
    const isCurrentVideo = currentVideoInfo && 
      (videoInfo.url === currentVideoInfo.url || 
       (videoInfo.videoTitle && currentVideoInfo.videoTitle && videoInfo.videoTitle === currentVideoInfo.videoTitle));
    
    let displayTitle;
    let titleClass = 'download-title';
    
    if (isCurrentVideo) {
      displayTitle = 'This video';
      titleClass += ' current-video';
    } else {
      displayTitle = title.length > 40 ? title.substring(0, 40) + '...' : title;
    }
    
    downloadItem.innerHTML = `
      <div class="${titleClass}" title="${title}">${displayTitle}</div>
      <div class="progress-text">Preparing download...</div>
      <div class="progress-bar">
        <div class="progress-fill" style="width: 0%"></div>
      </div>
      <div class="download-actions">
        <button class="cancel-btn" onclick="cancelDownload('${downloadId}')">
          ❌ Cancel
        </button>
      </div>
    `;
    
    return downloadItem;
  }
  
  function addDownloadToUI(downloadId, videoInfo) {
    // Show downloads section when adding first download
    if (downloadsSection && !downloadsSection.classList.contains('visible')) {
      downloadsSection.classList.add('visible');
      // Add class to body to trigger height increase
      document.body.classList.add('has-downloads');
    }
    
    // Hide empty state when adding first download
    if (downloadsEmpty) {
      downloadsEmpty.style.display = 'none';
    }
    
    const downloadElement = createDownloadElement(downloadId, videoInfo);
    downloadsContainer.appendChild(downloadElement);
    return downloadElement;
  }
  
  function updateDownloadProgress(downloadId, percent, status, speed = '', eta = '') {
    const downloadElement = document.getElementById(`download-${downloadId}`);
    if (!downloadElement) return;
    
    const progressFill = downloadElement.querySelector('.progress-fill');
    const progressText = downloadElement.querySelector('.progress-text');
    
    progressFill.style.width = `${percent}%`;
    
    // Normalize status to always show "Downloading" with capital D
    const normalizedStatus = status.toLowerCase() === 'downloading' ? 'Downloading' : status;
    
    // Clean up ETA by removing color codes and extra formatting
    let cleanEta = eta;
    if (eta) {
      // Remove ANSI color codes like [0;33m and [0m
      cleanEta = eta.replace(/\[[0-9;]*m/g, '');
    }
    
    // Simple format: "Downloading 20.4%" or "Downloading 20.4% - ETA: 12:41"
    let text = `${normalizedStatus} ${percent.toFixed(1)}%`;
    if (cleanEta) {
      text += ` - ETA: ${cleanEta}`;
    }
    
    progressText.textContent = text;
  }
  
  function removeDownloadFromUI(downloadId) {
    const downloadElement = document.getElementById(`download-${downloadId}`);
    if (downloadElement) {
      downloadElement.remove();
    }
    
    // Check if any actual download items remain (excluding empty state)
    const downloadItems = downloadsContainer.querySelectorAll('.download-item');
    
    if (downloadItems.length === 0) {
      // Hide entire downloads section when no downloads remain
      if (downloadsSection) {
        downloadsSection.classList.remove('visible');
        // Remove class from body to trigger height decrease
        document.body.classList.remove('has-downloads');
      }
    }
  }
  
  function markDownloadComplete(downloadId, status, errorMessage = '') {
    const downloadElement = document.getElementById(`download-${downloadId}`);
    if (!downloadElement) return;
    
    // Update visual state
    if (status === 'completed') {
      downloadElement.classList.add('download-completed');
      downloadElement.querySelector('.progress-text').textContent = 'Download completed!';
    } else if (status === 'error') {
      downloadElement.classList.add('download-error');
      const progressText = downloadElement.querySelector('.progress-text');
      progressText.textContent = errorMessage ? `Failed: ${errorMessage}` : 'Download failed';
    } else if (status === 'cancelled') {
      downloadElement.classList.add('download-cancelled');
      downloadElement.querySelector('.progress-text').textContent = 'Download cancelled';
    }
    
    // Update actions based on status
    const actions = downloadElement.querySelector('.download-actions');
    if (status === 'completed') {
      actions.innerHTML = `<div style="text-align: center; font-size: 11px; color: #666;">✅ Completed</div>`;
      // Auto-remove completed downloads after delay
      setTimeout(() => {
        removeDownloadFromUI(downloadId);
      }, 5000);
    } else if (status === 'error') {
      // Keep failed downloads with retry/delete options
      actions.innerHTML = `
        <button class="cancel-btn" onclick="retryDownload('${downloadId}')" style="background: #4caf50;" title="Retry download">
          🔄 Retry
        </button>
        <button class="cancel-btn" onclick="deleteDownload('${downloadId}')" title="Delete download and clean up files">
          🗑️ Delete
        </button>
      `;
    } else if (status === 'cancelled') {
      // Keep cancelled downloads with delete option
      actions.innerHTML = `
        <button class="cancel-btn" onclick="deleteDownload('${downloadId}')" title="Remove from list">
          🗑️ Remove
        </button>
      `;
      // Auto-remove cancelled downloads after longer delay
      setTimeout(() => {
        removeDownloadFromUI(downloadId);
      }, 10000);
    }
  }
  
  async function checkForActiveDownloads() {
    console.log('Checking for active downloads...');
    await loadActiveDownloads();
    
    if (activeDownloads.size === 0) {
      console.log('No stored downloads found');
      return;
    }
    
    console.log('Found stored downloads:', activeDownloads);
    
    let hasActiveDownloads = false;
    
    // Check each stored download with server
    for (const [downloadId, download] of activeDownloads) {
      try {
        const response = await fetch(`http://localhost:8080/progress/${downloadId}`);
        
        if (response.ok) {
          const progress = await response.json();
          console.log(`Server progress for ${downloadId}:`, progress);
          
          if (progress.status === 'downloading' || progress.status === 'processing' || progress.status === 'preparing') {
            // Resume tracking active download
            console.log(`Resuming tracking for ${downloadId}`);
            addDownloadToUI(downloadId, download.videoInfo);
            updateDownloadProgress(downloadId, progress.percent || 0, progress.status, progress.speed || '', progress.eta || '');
            hasActiveDownloads = true;
          } else {
            // Download finished while popup was closed
            console.log(`Download ${downloadId} finished while closed:`, progress.status);
            activeDownloads.delete(downloadId);
            
            if (progress.status === 'completed') {
              showStatus('✅ Download completed while popup was closed!', 'success');
            } else if (progress.status === 'error') {
              showStatus(`❌ Download failed: ${progress.error}`, 'error');
            }
          }
        } else {
          console.log(`Server doesn't have download ${downloadId}, removing from storage`);
          activeDownloads.delete(downloadId);
        }
      } catch (error) {
        console.log(`Error checking download ${downloadId}:`, error);
        activeDownloads.delete(downloadId);
      }
    }
    
    await saveActiveDownloads();
    
    // Start polling if we have active downloads
    if (activeDownloads.size > 0 && hasActiveDownloads) {
      startPolling();
    }
  }
  
  async function pollAllDownloads() {
    if (activeDownloads.size === 0) {
      stopPolling();
      return;
    }
    
    for (const downloadId of activeDownloads.keys()) {
      try {
        const response = await fetch(`http://localhost:8080/progress/${downloadId}`);
        
        if (response.ok) {
          const progress = await response.json();
          
          if (progress.status === 'downloading') {
            updateDownloadProgress(downloadId, progress.percent || 0, 'Downloading', progress.speed || '', progress.eta || '');
          } else if (progress.status === 'processing') {
            updateDownloadProgress(downloadId, 100, 'Processing...', '', '');
          } else if (progress.status === 'completed') {
            updateDownloadProgress(downloadId, 100, 'Completed!', '', '');
            markDownloadComplete(downloadId, 'completed');
            activeDownloads.delete(downloadId);
            
            // Show notification
            try {
              chrome.notifications.create({
                type: 'basic',
                iconUrl: 'icons/icon48.png',
                title: 'VidSnatch',
                message: 'Video download completed!'
              });
            } catch (e) {
              console.log('Notification failed:', e);
            }
            
          } else if (progress.status === 'error') {
            markDownloadComplete(downloadId, 'error', progress.error);
            // Don't delete from activeDownloads - keep for retry
            showStatus(`❌ Download failed: ${progress.error}`, 'error');
            
          } else if (progress.status === 'cancelled') {
            markDownloadComplete(downloadId, 'cancelled');
            activeDownloads.delete(downloadId);
          }
        } else {
          // Server doesn't have this download anymore
          activeDownloads.delete(downloadId);
          removeDownloadFromUI(downloadId);
        }
      } catch (error) {
        console.error(`Error polling download ${downloadId}:`, error);
      }
    }
    
    await saveActiveDownloads();
  }
  
  function stopPolling() {
    if (progressInterval) {
      clearInterval(progressInterval);
      progressInterval = null;
    }
  }
  
  function startPolling() {
    stopPolling(); // Clear any existing polling
    progressInterval = setInterval(async () => {
      await pollAllDownloads();
    }, 1000);
  }
  
  function updateToggleUI() {
    if (openFolderEnabled) {
      openFolderToggle.classList.add('active');
    } else {
      openFolderToggle.classList.remove('active');
    }
  }
  
  function updateUI(videoInfo) {
    if (!videoInfo) {
      currentUrlDiv.textContent = 'No video information available';
      downloadBtn.disabled = true;
      return;
    }
    
    // Display URL info with cleaned title
    const rawUrlText = videoInfo.videoTitle || videoInfo.title || videoInfo.url;
    const cleanUrlText = rawUrlText === videoInfo.url ? rawUrlText : cleanVideoTitle(rawUrlText);
    currentUrlDiv.textContent = cleanUrlText.length > 100 ? 
      cleanUrlText.substring(0, 100) + '...' : cleanUrlText;
    
    // Enable/disable download button based on video detection
    const isLikelyVideo = videoInfo.isVideoSite || videoInfo.hasVideoElements || videoInfo.hasVideoKeywords;
    downloadBtn.disabled = !isLikelyVideo;
    
    if (isLikelyVideo) {
      showStatus('Video detected! Ready to download.', 'success');
    } else {
      showStatus('No video detected on this page.', 'info');
    }
  }
  
  function showStatus(message, type = 'info') {
    statusDiv.textContent = message;
    statusDiv.className = `status ${type}`;
    
    // Clear status after 3 seconds unless it's an error
    if (type !== 'error') {
      setTimeout(() => {
        statusDiv.textContent = '';
        statusDiv.className = 'status';
      }, 3000);
    }
  }
  
  // Download button click handler
  downloadBtn.addEventListener('click', async function() {
    if (!currentVideoInfo || !currentVideoInfo.url) {
      showStatus('No URL to download', 'error');
      return;
    }
    
    try {
      // Send URL to local Quikvid-DL server
      const response = await fetch('http://localhost:8080/download', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          url: currentVideoInfo.url,
          title: cleanVideoTitle(currentVideoInfo.videoTitle || currentVideoInfo.title),
          openFolder: openFolderEnabled
        })
      });
      
      if (response.ok) {
        const result = await response.json();
        const downloadId = result.downloadId;
        
        // Add to active downloads
        activeDownloads.set(downloadId, {
          downloadId: downloadId,
          videoInfo: currentVideoInfo,
          timestamp: Date.now()
        });
        
        // Save to storage
        await saveActiveDownloads();
        
        // Add to UI
        addDownloadToUI(downloadId, currentVideoInfo);
        
        // Start polling if not already running
        if (!progressInterval) {
          startPolling();
        }
        
        showStatus('Download started!', 'success');
        
      } else {
        throw new Error(`Server responded with ${response.status}`);
      }
      
    } catch (error) {
      console.error('Download error:', error);
      
      if (error.message.includes('Failed to fetch')) {
        showStatus('❌ Quikvid-DL server not running. Start the application first.', 'error');
      } else {
        showStatus(`❌ Download failed: ${error.message}`, 'error');
      }
    }
  });
  
  // Global cancel function for onclick handlers
  window.cancelDownload = async function(downloadId) {
    try {
      const response = await fetch(`http://localhost:8080/cancel/${downloadId}`, {
        method: 'POST'
      });
      
      if (response.ok) {
        showStatus('Cancelling download...', 'info');
        updateDownloadProgress(downloadId, 0, 'Cancelling...', '', '');
      } else {
        showStatus('Failed to cancel download', 'error');
      }
      
    } catch (error) {
      console.error('Cancel error:', error);
      showStatus('Error cancelling download', 'error');
    }
  };

  // Global retry function
  window.retryDownload = async function(downloadId) {
    try {
      const response = await fetch(`http://localhost:8080/retry/${downloadId}`, {
        method: 'POST'
      });
      
      const result = await response.json();
      
      if (result.success) {
        showStatus(`🔄 Retrying download (attempt #${result.retry_count})...`, 'info');
        
        // Reset the download element to preparing state
        const downloadElement = document.getElementById(`download-${downloadId}`);
        if (downloadElement) {
          downloadElement.classList.remove('download-error', 'download-cancelled');
          downloadElement.querySelector('.progress-text').textContent = 'Preparing retry...';
          const progressFill = downloadElement.querySelector('.progress-fill');
          progressFill.style.width = '0%';
          
          // Update actions back to cancel button
          const actions = downloadElement.querySelector('.download-actions');
          actions.innerHTML = `
            <button class="cancel-btn" onclick="cancelDownload('${downloadId}')">
              ❌ Cancel
            </button>
          `;
        }
        
        // Start polling again
        if (!progressInterval) {
          startPolling();
        }
      } else {
        showStatus(`❌ Retry failed: ${result.error}`, 'error');
      }
      
    } catch (error) {
      console.error('Retry error:', error);
      showStatus('Error retrying download', 'error');
    }
  };

  // Global delete function
  window.deleteDownload = async function(downloadId) {
    try {
      const response = await fetch(`http://localhost:8080/delete/${downloadId}`, {
        method: 'POST'
      });
      
      const result = await response.json();
      
      if (result.success) {
        showStatus(`🗑️ Download deleted${result.removedFiles?.length ? ' and partial files cleaned up' : ''}`, 'info');
        
        // Remove from UI and active downloads
        removeDownloadFromUI(downloadId);
        activeDownloads.delete(downloadId);
        await saveActiveDownloads();
        
      } else {
        showStatus(`❌ Delete failed: ${result.error}`, 'error');
      }
      
    } catch (error) {
      console.error('Delete error:', error);
      showStatus('Error deleting download', 'error');
    }
  };
  
  // Open folder toggle handler
  openFolderToggle.addEventListener('click', function() {
    openFolderEnabled = !openFolderEnabled;
    updateToggleUI();
    saveSettings();
    
    const status = openFolderEnabled ? 'enabled' : 'disabled';
    showStatus(`Folder opening ${status}`, 'info');
  });
  
  // Folder path click handler with debounce
  folderPath.addEventListener('click', async function() {
    // Prevent multiple simultaneous folder selections
    if (folderSelectionInProgress) {
      console.log('Folder selection already in progress, ignoring click');
      return;
    }
    
    try {
      folderSelectionInProgress = true;
      
      // Visual feedback - disable and show loading state
      folderPath.style.pointerEvents = 'none';
      folderPath.style.opacity = '0.6';
      folderPath.textContent = 'Opening folder selector...';
      folderPath.title = 'Please wait...';
      
      showStatus('Opening folder selector...', 'info');
      
      const response = await fetch('http://localhost:8080/select-folder', {
        method: 'POST'
      });
      
      if (response.ok) {
        const result = await response.json();
        if (result.success && result.path) {
          updateFolderPathDisplay(result.path);
          showStatus('✅ Download folder updated!', 'success');
        } else if (result.cancelled) {
          showStatus('Folder selection cancelled', 'info');
          // Reload the original path since user cancelled
          await loadCurrentFolderPath();
        } else {
          showStatus('❌ Failed to change folder', 'error');
          // Reload the original path on error
          await loadCurrentFolderPath();
        }
      } else {
        showStatus('❌ Server error changing folder', 'error');
        // Reload the original path on error
        await loadCurrentFolderPath();
      }
    } catch (error) {
      console.error('Error changing folder:', error);
      showStatus('❌ Error opening folder selector', 'error');
      // Reload the original path on error
      await loadCurrentFolderPath();
    } finally {
      // Re-enable the folder path click after a short delay
      setTimeout(() => {
        folderSelectionInProgress = false;
        folderPath.style.pointerEvents = 'auto';
        folderPath.style.opacity = '1';
      }, 500); // 500ms delay to prevent rapid clicking
    }
  });
  
  // Open folder button click handler
  openFolderBtn.addEventListener('click', async function() {
    try {
      openFolderBtn.disabled = true;
      showStatus('Opening download folder...', 'info');
      
      const response = await fetch('http://localhost:8080/open-folder', {
        method: 'POST'
      });
      
      if (response.ok) {
        const result = await response.json();
        if (result.success) {
          showStatus('✅ Folder opened!', 'success');
        } else {
          showStatus('❌ Failed to open folder', 'error');
        }
      } else {
        showStatus('❌ Server error opening folder', 'error');
      }
    } catch (error) {
      console.error('Error opening folder:', error);
      showStatus('❌ Error opening folder', 'error');
    } finally {
      // Re-enable button after short delay
      setTimeout(() => {
        openFolderBtn.disabled = false;
      }, 1000);
    }
  });
  
  // Settings button click handler
  settingsBtn.addEventListener('click', function() {
    chrome.tabs.create({ url: 'chrome://extensions/?id=' + chrome.runtime.id });
  });
  
  // Server control button handler
  stopServerBtn.addEventListener('click', stopServer);
  
  // Initialize
  await getCurrentTabInfo();
});