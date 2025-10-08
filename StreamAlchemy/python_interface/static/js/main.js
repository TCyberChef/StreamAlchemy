document.addEventListener('DOMContentLoaded', function() {
    // Element constants
    const streamForm = document.getElementById('streamForm');
    const streamNameInput = document.getElementById('stream_name');
    const sourceUrlInput = document.getElementById('source_url'); 
    const videoFileSelect = document.getElementById('video_file');
    const videoFilePath = document.getElementById('video_file_path');
    const submitButton = streamForm ? streamForm.querySelector('button[type="submit"]') : null;

    // Upload Modal Elements
    const uploadModalBtn = document.getElementById('uploadToBrowseableBtn');
    const uploadModalElement = document.getElementById('uploadModal');
    const uploadModalForm = document.getElementById('uploadModalForm');
    const uploadModalSubmitBtn = document.getElementById('uploadModalSubmitBtn');
    const uploadModalAlerts = document.getElementById('uploadModalAlerts');
    const uploadFileModalInput = document.getElementById('uploadFileModalInput');
    let bsUploadModal = null;
    // Progress Bar Elements
    const uploadProgressContainer = document.getElementById('uploadProgressContainer');
    const uploadProgressBar = document.getElementById('uploadProgressBar');

    if (uploadModalElement) {
        bsUploadModal = new bootstrap.Modal(uploadModalElement);
    }

    // Client-side file size check for upload modal
    if (uploadFileModalInput && uploadModalSubmitBtn && uploadModalAlerts) {
        const maxSizeBytes = parseInt(uploadFileModalInput.dataset.maxSize, 10);
        const maxSizeMB = Math.round(maxSizeBytes / (1024 * 1024));

        async function checkAndReportFileStatus(file) {
            if (!file) {
                uploadModalSubmitBtn.disabled = true; // Disable if no file
                if(uploadModalAlerts && uploadModalAlerts.querySelector('.alert-info')) {
                    uploadModalAlerts.innerHTML = '';
                }
                return;
            }

            let sizeOk = true;
            let existsMessage = '';
            let infoMessage = `Selected file: ${file.name} (${(file.size / (1024*1024)).toFixed(2)} MB).`;

            // 1. Check size
            if (file.size > maxSizeBytes) {
                infoMessage = `<div class="alert alert-danger">File is too large (${(file.size / (1024*1024)).toFixed(2)} MB). Maximum size is ${maxSizeMB} MB.</div>`;
                uploadModalSubmitBtn.disabled = true;
                sizeOk = false;
            } else {
                uploadModalSubmitBtn.disabled = false; // Enable if size is okay
            }

            // 2. If size is OK, check existence (only if a file is actually selected)
            if (sizeOk && file.name) {
                try {
                    // Use encodeURIComponent for the filename in the URL
                    const response = await fetch(`/check_file_exists/${encodeURIComponent(file.name)}`);
                    const data = await response.json();
                    if (data.exists) {
                        existsMessage = `<div class="alert alert-warning mt-2"><strong>Warning:</strong> File "${data.checked_name}" already exists and will be overwritten.</div>`;
                        // Keep button enabled for overwrite, or set uploadModalSubmitBtn.disabled = true; to block
                    }
                } catch (error) {
                    console.error("Error checking file existence:", error);
                    existsMessage = `<div class="alert alert-secondary mt-2">Could not verify if file exists.</div>`;
                }
            }
            
            if(uploadModalAlerts) {
                uploadModalAlerts.innerHTML = infoMessage + existsMessage;
            }
        }

        uploadFileModalInput.addEventListener('change', function(event) {
            const file = event.target.files[0];
            checkAndReportFileStatus(file);
        });
    }

    // Function to extract filename without extension for stream name
    function getFilenameWithoutExtension(path) {
        if (!path) return '';
        // Get the filename from the path (handles both file paths and just filenames)
        const filename = path.split('/').pop().split('\\').pop();
        // Remove the file extension
        const lastDotIndex = filename.lastIndexOf('.');
        if (lastDotIndex > 0) {
            return filename.substring(0, lastDotIndex);
        }
        return filename;
    }

    // Function to load video files into the dropdown
    function loadVideoFiles() {
        const currentVideoFileSelect = document.getElementById('video_file');
        const videoSearchInput = document.getElementById('video_file_search');
        const videoDropdown = document.getElementById('video_file_dropdown');
        const fromFolderLabel = document.querySelector('label[for="file_source_folder"]'); // Get the label for the tooltip

        if (!currentVideoFileSelect || !videoSearchInput || !videoDropdown) {
            // console.error("Required elements not found by loadVideoFiles");
            return;
        }

        let allVideos = []; // Store all videos for filtering

        fetch("/list_videos")
            .then(response => response.json())
            .then(data => {
                let browseDir = data.browse_directory || '[Default Browseable Folder]'; // Get browse_dir from response
                
                if (fromFolderLabel) {
                    fromFolderLabel.title = `Scans: ${browseDir}`; // Set tooltip on hover
                }

                if (data.success) {
                    allVideos = data.videos || [];
                    if (allVideos.length > 0) {
                        videoSearchInput.placeholder = "Type to search files...";
                        renderVideoDropdown(allVideos, ''); // Render all videos initially
                    } else {
                        videoDropdown.innerHTML = `<div class="dropdown-item no-results">No videos found in ${browseDir}</div>`;
                    }
                } else {
                    videoDropdown.innerHTML = '<div class="dropdown-item no-results">Error loading videos</div>';
                }
            })
            .catch(error => {
                // console.error('Fetch error loading video files:', error);
                if (fromFolderLabel) {
                    fromFolderLabel.title = 'Error fetching browseable folder path';
                }
                videoDropdown.innerHTML = '<div class="dropdown-item no-results">Error fetching videos</div>';
            });

        // Function to render dropdown items with search filtering
        function renderVideoDropdown(videos, searchTerm) {
            const filteredVideos = filterVideos(videos, searchTerm);
            videoDropdown.innerHTML = '';

            if (filteredVideos.length === 0) {
                const noResultsItem = document.createElement('div');
                noResultsItem.className = 'dropdown-item no-results';
                noResultsItem.textContent = searchTerm ? 'No matching files found' : 'Select a video from server...';
                videoDropdown.appendChild(noResultsItem);
                return;
            }

            filteredVideos.forEach(video => {
                const item = document.createElement('div');
                item.className = 'dropdown-item';
                item.dataset.path = video.path;
                item.innerHTML = highlightMatches(video.name, searchTerm);
                
                item.addEventListener('click', function() {
                    selectVideo(video.path, video.name);
                });
                
                videoDropdown.appendChild(item);
            });
        }

        // Function to filter videos based on search term (anywhere in filename)
        function filterVideos(videos, searchTerm) {
            if (!searchTerm.trim()) {
                return videos;
            }
            
            const term = searchTerm.toLowerCase();
            return videos.filter(video => 
                video.name.toLowerCase().includes(term)
            );
        }

        // Function to highlight matching text
        function highlightMatches(text, searchTerm) {
            if (!searchTerm.trim()) {
                return text;
            }
            
            const term = searchTerm.toLowerCase();
            const lowerText = text.toLowerCase();
            const index = lowerText.indexOf(term);
            
            if (index === -1) {
                return text;
            }
            
            const before = text.substring(0, index);
            const match = text.substring(index, index + term.length);
            const after = text.substring(index + term.length);
            
            return before + '<span class="highlight">' + match + '</span>' + after;
        }

        // Function to select a video
        function selectVideo(path, name) {
            currentVideoFileSelect.value = path;
            videoSearchInput.value = name;
            videoDropdown.style.display = 'none';
            
            // Auto-populate stream name with filename without extension
            const streamNameInput = document.getElementById('stream_name');
            if (streamNameInput && !streamNameInput.value.trim()) {
                streamNameInput.value = getFilenameWithoutExtension(name);
                // Trigger validation for the stream name
                const inputEvent = new Event('input', { bubbles: true });
                streamNameInput.dispatchEvent(inputEvent);
            }
            
            checkFormValidityAndUpdateButton();
            
            // Trigger change event for any other listeners
            const changeEvent = new Event('change', { bubbles: true });
            currentVideoFileSelect.dispatchEvent(changeEvent);
        }

        // Search input event handler
        let searchTimeout;
        videoSearchInput.addEventListener('input', function() {
            const searchTerm = this.value;
            
            // Clear previous timeout
            clearTimeout(searchTimeout);
            
            // Debounce search to avoid too many updates
            searchTimeout = setTimeout(() => {
                renderVideoDropdown(allVideos, searchTerm);
                
                if (searchTerm) {
                    videoDropdown.style.display = 'block';
                } else {
                    videoDropdown.style.display = 'none';
                    currentVideoFileSelect.value = '';
                    checkFormValidityAndUpdateButton();
                }
            }, 150);
        });

        // Show dropdown on focus
        videoSearchInput.addEventListener('focus', function() {
            if (allVideos.length > 0) {
                videoDropdown.style.display = 'block';
            }
        });

        // Keyboard navigation
        let selectedIndex = -1;
        videoSearchInput.addEventListener('keydown', function(e) {
            const items = videoDropdown.querySelectorAll('.dropdown-item:not(.no-results):not(.loading-item)');
            
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                selectedIndex = Math.min(selectedIndex + 1, items.length - 1);
                updateSelection(items);
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                selectedIndex = Math.max(selectedIndex - 1, -1);
                updateSelection(items);
            } else if (e.key === 'Enter') {
                e.preventDefault();
                if (selectedIndex >= 0 && items[selectedIndex]) {
                    items[selectedIndex].click();
                }
            } else if (e.key === 'Escape') {
                videoDropdown.style.display = 'none';
                selectedIndex = -1;
            } else {
                selectedIndex = -1; // Reset selection when typing
            }
        });

        function updateSelection(items) {
            items.forEach((item, index) => {
                if (index === selectedIndex) {
                    item.classList.add('selected');
                    item.scrollIntoView({ block: 'nearest' });
                } else {
                    item.classList.remove('selected');
                }
            });
        }

        // Hide dropdown when clicking outside
        document.addEventListener('click', function(e) {
            if (!videoSearchInput.contains(e.target) && !videoDropdown.contains(e.target)) {
                videoDropdown.style.display = 'none';
                selectedIndex = -1;
            }
        });
    }

    // Audio settings toggle
    const audioEnabledYes = document.getElementById('audio_enabled_yes');
    const audioEnabledNo = document.getElementById('audio_enabled_no');
    const audioCodecContainer = document.getElementById('audio_codec_container');
    
    if (audioEnabledYes && audioEnabledNo && audioCodecContainer) {
        audioCodecContainer.style.display = audioEnabledYes.checked ? 'block' : 'none';
        audioEnabledYes.addEventListener('change', function() { audioCodecContainer.style.display = 'block'; });
        audioEnabledNo.addEventListener('change', function() { audioCodecContainer.style.display = 'none'; });
    }

    // Stream type toggle
    const streamTypeRtsp = document.getElementById('stream_type_rtsp');
    const streamTypeFile = document.getElementById('stream_type_file');
    const rtspSourceContainer = document.getElementById('rtsp_source_container');
    const fileSourceContainer = document.getElementById('file_source_container');

    // File source type elements (for direct manipulation)
    const fileSourceFolderRadio = document.getElementById('file_source_folder');
    const fileSourceCustomRadio = document.getElementById('file_source_custom');
    const folderSelectionDiv = document.getElementById('folder_selection');
    const customPathDiv = document.getElementById('custom_path');
    const fileSourceTypeGroup = fileSourceFolderRadio ? fileSourceFolderRadio.closest('.btn-group') : null;

    function handleFileSourceTypeChange() {
        if (!fileSourceFolderRadio || !fileSourceCustomRadio || !folderSelectionDiv || !customPathDiv || !videoFileSelect || !videoFilePath) return;
        if (fileSourceFolderRadio.checked) {
            folderSelectionDiv.style.display = 'block';
            customPathDiv.style.display = 'none';
            videoFileSelect.required = true;
            videoFilePath.required = false;
        } else { // Custom path selected
            folderSelectionDiv.style.display = 'none';
            customPathDiv.style.display = 'block';
            videoFileSelect.required = false;
            videoFilePath.required = true;
        }
        checkFormValidityAndUpdateButton();
    }

    function handleStreamTypeChange() {
        if (!rtspSourceContainer || !fileSourceContainer || !sourceUrlInput || !videoFileSelect || !videoFilePath || !fileSourceTypeGroup) return;
        if (streamTypeRtsp.checked) {
            rtspSourceContainer.style.display = 'block';
            fileSourceContainer.style.display = 'none';
            sourceUrlInput.required = true;
            videoFileSelect.required = false;
            videoFilePath.required = false;
            fileSourceTypeGroup.style.display = 'block'; // Ensure this is visible if we go back and forth
        } else { // File type selected
            rtspSourceContainer.style.display = 'none';
            fileSourceContainer.style.display = 'block';
            sourceUrlInput.required = false;
            fileSourceTypeGroup.style.display = 'block'; // Make sure radio buttons for folder/custom are visible
            handleFileSourceTypeChange(); // Call this to set sub-section visibility and required fields
        }
        checkFormValidityAndUpdateButton();
    }

    if (streamTypeRtsp && streamTypeFile) {
        streamTypeRtsp.addEventListener('change', handleStreamTypeChange);
        streamTypeFile.addEventListener('change', handleStreamTypeChange);
    }
    if (fileSourceFolderRadio && fileSourceCustomRadio) {
        fileSourceFolderRadio.addEventListener('change', handleFileSourceTypeChange);
        fileSourceCustomRadio.addEventListener('change', handleFileSourceTypeChange);
    }

    // Initial UI state setup
    if (streamTypeRtsp && streamTypeRtsp.checked) {
        handleStreamTypeChange(); 
    } else if (streamTypeFile && streamTypeFile.checked) {
        handleStreamTypeChange(); 
    } else { // Default if nothing checked (should not happen with 'checked' in HTML)
        if(rtspSourceContainer) rtspSourceContainer.style.display = 'block';
        if(fileSourceContainer) fileSourceContainer.style.display = 'none';
    }
    // Also call handleFileSourceTypeChange initially if file type is selected by default, 
    // to set the sub-display (folder/custom) correctly.
    // handleStreamTypeChange already calls it if file type is active.

    // --- Upload Modal Logic ---
    if (uploadModalBtn && bsUploadModal) {
        uploadModalBtn.addEventListener('click', function() {
            if(uploadModalAlerts) uploadModalAlerts.innerHTML = ''; // Clear previous alerts
            if(uploadFileModalInput) uploadFileModalInput.value = ''; // Clear previous file selection
            if(uploadModalSubmitBtn) {
                uploadModalSubmitBtn.disabled = false;
                uploadModalSubmitBtn.innerHTML = '<i class="fas fa-upload"></i> Upload';
            }
            bsUploadModal.show();
        });
    }

    if (uploadModalForm && uploadModalSubmitBtn) {
        uploadModalForm.addEventListener('submit', function(e) {
            e.preventDefault();
            // Double check file input and size before actual submission, though primary check is on 'change'
            if (!uploadFileModalInput || !uploadFileModalInput.files || uploadFileModalInput.files.length === 0) {
                if(uploadModalAlerts && !uploadModalAlerts.querySelector('.alert-danger')) { // Avoid duplicate message if already shown by change listener
                    uploadModalAlerts.innerHTML = '<div class="alert alert-danger">Please select a file to upload.</div>';
                }
                return;
            }
            const file = uploadFileModalInput.files[0];
            const maxSizeBytes = parseInt(uploadFileModalInput.dataset.maxSize, 10);
            if (file.size > maxSizeBytes) {
                 if(uploadModalAlerts && !uploadModalAlerts.innerHTML.includes('File is too large')) { // Avoid duplicate message
                    const maxSizeMB = Math.round(maxSizeBytes / (1024 * 1024));
                    uploadModalAlerts.innerHTML = 
                        `<div class="alert alert-danger">File is too large (${(file.size / (1024*1024)).toFixed(2)} MB). Maximum size is ${maxSizeMB} MB. Cannot upload.</div>`;
                }
                uploadModalSubmitBtn.disabled = true; // Ensure button is disabled
                return; // Prevent upload
            }

            const formData = new FormData(this);
            const originalButtonText = uploadModalSubmitBtn.innerHTML;
            uploadModalSubmitBtn.disabled = true;
            uploadModalSubmitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Uploading...';
            if(uploadModalAlerts) uploadModalAlerts.innerHTML = '';
            
            // Show and reset progress bar
            if (uploadProgressContainer) uploadProgressContainer.style.display = 'block';
            if (uploadProgressBar) {
                uploadProgressBar.style.width = '0%';
                uploadProgressBar.textContent = '0%';
                uploadProgressBar.setAttribute('aria-valuenow', '0');
            }

            const xhr = new XMLHttpRequest();
            xhr.open('POST', '/uploader', true);

            xhr.upload.onprogress = function(event) {
                if (event.lengthComputable) {
                    const percentComplete = Math.round((event.loaded / event.total) * 100);
                    if (uploadProgressBar) {
                        uploadProgressBar.style.width = percentComplete + '%';
                        uploadProgressBar.textContent = percentComplete + '%';
                        uploadProgressBar.setAttribute('aria-valuenow', percentComplete);
                    }
                }
            };

            xhr.onload = function() {
                uploadModalSubmitBtn.disabled = false;
                uploadModalSubmitBtn.innerHTML = originalButtonText;
                if (uploadProgressContainer) {
                     // Keep progress bar at 100% on success or show error state
                }

                if (xhr.status >= 200 && xhr.status < 300) {
                    try {
                        const data = JSON.parse(xhr.responseText);
                        if (data.success) {
                            if(uploadModalAlerts) {
                                uploadModalAlerts.innerHTML = `<div class="alert alert-success">${data.message}</div>`;
                            }
                            if(uploadFileModalInput) uploadFileModalInput.value = '';
                            loadVideoFiles();
                            if (uploadProgressBar) {
                                uploadProgressBar.classList.remove('bg-danger');
                                uploadProgressBar.classList.add('bg-success');
                                uploadProgressBar.textContent = 'Uploaded!';
                            }
                            // setTimeout(() => { 
                            //     if(bsUploadModal) bsUploadModal.hide(); 
                            //     if (uploadProgressContainer) uploadProgressContainer.style.display = 'none';
                            // }, 2000);
                        } else {
                            if(uploadModalAlerts) {
                                uploadModalAlerts.innerHTML = `<div class="alert alert-danger">Error: ${data.message || 'Unknown upload error.'}</div>`;
                            }
                            if (uploadProgressBar) {
                                uploadProgressBar.classList.add('bg-danger');
                                uploadProgressBar.textContent = 'Upload Failed';
                            }
                        }
                    } catch (ex) {
                        if(uploadModalAlerts) {
                            uploadModalAlerts.innerHTML = `<div class="alert alert-danger">Error parsing server response.</div>`;
                        }
                        if (uploadProgressBar) {
                            uploadProgressBar.classList.add('bg-danger');
                            uploadProgressBar.textContent = 'Error';
                        }
                    }
                } else {
                    if(uploadModalAlerts) {
                        uploadModalAlerts.innerHTML = `<div class="alert alert-danger">Server error: ${xhr.status} ${xhr.statusText}</div>`;
                    }
                     if (uploadProgressBar) {
                        uploadProgressBar.classList.add('bg-danger');
                        uploadProgressBar.textContent = 'Server Error';
                    }
                }
            };

            xhr.onerror = function() {
                uploadModalSubmitBtn.disabled = false;
                uploadModalSubmitBtn.innerHTML = originalButtonText;
                if(uploadModalAlerts) {
                    uploadModalAlerts.innerHTML = `<div class="alert alert-danger">Network Error: Could not connect to server.</div>`;
                }
                if (uploadProgressContainer) uploadProgressContainer.style.display = 'block'; // Keep visible on error
                if (uploadProgressBar) {
                    uploadProgressBar.style.width = '100%'; // Show full bar as red
                    uploadProgressBar.classList.add('bg-danger');
                    uploadProgressBar.textContent = 'Network Error';
                }
            };

            xhr.onabort = function() {
                uploadModalSubmitBtn.disabled = false;
                uploadModalSubmitBtn.innerHTML = originalButtonText;
                if(uploadModalAlerts) {
                    uploadModalAlerts.innerHTML = `<div class="alert alert-warning">Upload aborted.</div>`;
                }
                if (uploadProgressContainer) uploadProgressContainer.style.display = 'none';
            };
            
            // Send the FormData object
            xhr.send(formData);
        });
    }
    // --- End Upload Modal Logic ---

    function validateStreamName(name) {
        const validPattern = /^[a-zA-Z0-9_-]+$/;
        return validPattern.test(name);
    }
    function validateSourceUrl(url) {
        const validPattern = /^(rtsp|https?):\/\/.+/i;
        try { new URL(url); return validPattern.test(url); } catch (e) { return false; }
    }
    function validateFilePath(path) {
        return path && path.trim().length > 0 && !path.includes('\0');
    }

    function showAlert(type, title, message) {
        const alertBoxGlobal = document.getElementById('alertBox');
        if (!alertBoxGlobal) { /* console.error("Global alertBox not found"); */ return; }
        alertBoxGlobal.innerHTML = '';
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type === 'error' ? 'danger' : 'success'} alert-dismissible fade show`;
        alertDiv.setAttribute('role', 'alert');
        alertDiv.innerHTML = `<strong>${title}</strong> ${message}<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>`;
        alertBoxGlobal.appendChild(alertDiv);
        alertBoxGlobal.style.display = 'block';
        setTimeout(() => {
            const instance = bootstrap.Alert.getInstance(alertDiv);
            if (instance) instance.close();
            else if (alertBoxGlobal.contains(alertDiv)) { 
                alertDiv.classList.remove('show'); 
                setTimeout(() => { if (alertBoxGlobal.contains(alertDiv)) alertBoxGlobal.removeChild(alertDiv); }, 150);
            }
        }, 7000);
    }

    function updateValidationState(input, isValid, errorMessage) {
        if (!input) return;
        const parentNode = input.parentNode;
        let feedbackDiv = parentNode.querySelector('.invalid-feedback');
        if (!feedbackDiv && (input.type === 'select-one' || input.type === 'text' || input.type === 'checkbox' || input.type === 'radio')) {
            feedbackDiv = document.createElement('div');
            feedbackDiv.className = 'invalid-feedback';
            if (input.parentNode.classList.contains('form-check')) {
                 input.parentNode.parentNode.appendChild(feedbackDiv);
            } else {
                 input.parentNode.appendChild(feedbackDiv);
            }
        }
        
        if (!isValid) {
            input.classList.add('is-invalid');
            input.classList.remove('is-valid');
            if(feedbackDiv) feedbackDiv.textContent = errorMessage;
            if(feedbackDiv) feedbackDiv.style.display = 'block';
        } else {
            input.classList.remove('is-invalid');
            input.classList.add('is-valid');
            if(feedbackDiv) feedbackDiv.textContent = '';
            if(feedbackDiv) feedbackDiv.style.display = 'none';
        }
        checkFormValidityAndUpdateButton();
    }
    
    function checkFormValidityAndUpdateButton() {
        if (!submitButton || !streamNameInput ) return;

        const currentStreamTypeRadio = document.querySelector('input[name="stream_type"]:checked');
        if (!currentStreamTypeRadio) return; // Should not happen
        const currentStreamType = currentStreamTypeRadio.value;

        const isNameValid = validateStreamName(streamNameInput.value.trim()) && streamNameInput.value.trim() !== '';
        let isSourceValid = false;

        if (currentStreamType === 'rtsp') {
            isSourceValid = sourceUrlInput && validateSourceUrl(sourceUrlInput.value.trim()) && sourceUrlInput.value.trim() !== '';
        } else { 
            const fileSourceTypeRadio = document.querySelector('input[name="file_source_type"]:checked');
            if (fileSourceTypeRadio) {
                const fileSourceType = fileSourceTypeRadio.value;
                if (fileSourceType === 'folder') {
                    isSourceValid = videoFileSelect && videoFileSelect.value !== '';
                } else { 
                    isSourceValid = videoFilePath && validateFilePath(videoFilePath.value.trim());
                }
            } else { 
                 isSourceValid = false;
            }
        }
        const allValid = isNameValid && isSourceValid;
        submitButton.disabled = !allValid;

        let tooltipText = '';
        if (!isNameValid) tooltipText = 'Valid stream name required (no spaces, only letters, numbers, _, -).';
        else if (!isSourceValid) {
            if (currentStreamType === 'rtsp') {
                tooltipText = 'Valid RTSP or HTTP(S) URL required.';
            } else {
                const fileSourceTypeRadio = document.querySelector('input[name="file_source_type"]:checked');
                const fileSourceType = fileSourceTypeRadio ? fileSourceTypeRadio.value : 'folder';
                tooltipText = fileSourceType === 'folder' ? 'Video file selection required.' : 'Please enter a valid file path.';
            }
        }

        const existingTooltipInstance = bootstrap.Tooltip.getInstance(submitButton);
        if (existingTooltipInstance) {
            existingTooltipInstance.dispose(); 
        }

        if (tooltipText) {
            submitButton.setAttribute('title', tooltipText);
            new bootstrap.Tooltip(submitButton, {placement: 'top', trigger: 'hover'}); 
        } else {
            submitButton.removeAttribute('title');
        }
    }

    if (streamNameInput) {
        streamNameInput.addEventListener('input', function() {
            const val = this.value.trim();
            updateValidationState(this, validateStreamName(val), 'Use letters, numbers, underscores, hyphens. No spaces.');
        });
    }
    if (sourceUrlInput) {
        sourceUrlInput.addEventListener('input', function() {
            if (document.getElementById('stream_type_rtsp').checked) {
                 const val = this.value.trim();
                 updateValidationState(this, validateSourceUrl(val), 'Valid RTSP or HTTP(S) URL. e.g., rtsp://...');
            }
        });
    }
    if (videoFileSelect) {
        videoFileSelect.addEventListener('change', function() {
             const streamTypeFileRadio = document.getElementById('stream_type_file');
             const fileSourceFolderRadio = document.getElementById('file_source_folder');
             if (streamTypeFileRadio && streamTypeFileRadio.checked && fileSourceFolderRadio && fileSourceFolderRadio.checked) {
                updateValidationState(this, this.value !== '', 'Please select a video file.');
            }
        });
    }
    if (videoFilePath) {
        videoFilePath.addEventListener('input', function() {
            const streamTypeFileRadio = document.getElementById('stream_type_file');
            const fileSourceCustomRadio = document.getElementById('file_source_custom');
            if (streamTypeFileRadio && streamTypeFileRadio.checked && fileSourceCustomRadio && fileSourceCustomRadio.checked) {
                updateValidationState(this, validateFilePath(this.value.trim()), 'Please enter a valid file path.');
                
                // Auto-populate stream name with filename without extension
                const streamNameInput = document.getElementById('stream_name');
                if (streamNameInput && !streamNameInput.value.trim() && this.value.trim()) {
                    const filename = getFilenameWithoutExtension(this.value.trim());
                    if (filename) {
                        streamNameInput.value = filename;
                        // Trigger validation for the stream name
                        const inputEvent = new Event('input', { bubbles: true });
                        streamNameInput.dispatchEvent(inputEvent);
                    }
                }
            }
        });
    }

    document.querySelectorAll('input[name="stream_type"]').forEach(radio => {
        radio.addEventListener('change', () => {
            if (radio.value === 'rtsp' && sourceUrlInput && sourceUrlInput.value) sourceUrlInput.dispatchEvent(new Event('input'));
            else if (radio.value === 'file') { 
                const fileSourceTypeRadio = document.querySelector('input[name="file_source_type"]:checked');
                if (fileSourceTypeRadio) { // Trigger validation on the active file input
                    if (fileSourceTypeRadio.value === 'folder' && videoFileSelect) {
                         videoFileSelect.dispatchEvent(new Event('change'));
                    } else if (fileSourceTypeRadio.value === 'custom' && videoFilePath) {
                         videoFilePath.dispatchEvent(new Event('input'));
                    }
                }
            }
            handleStreamTypeChange(); // To toggle sections
            // checkFormValidityAndUpdateButton(); // handleStreamTypeChange calls this
        });
    });
     document.querySelectorAll('input[name="file_source_type"]').forEach(radio => {
        radio.addEventListener('change', () => {
            if (radio.value === 'folder' && videoFileSelect ) videoFileSelect.dispatchEvent(new Event('change'));
            else if (radio.value === 'custom' && videoFilePath) videoFilePath.dispatchEvent(new Event('input'));
            handleStreamTypeChange(); // To toggle sections
            // checkFormValidityAndUpdateButton(); // handleFileSourceTypeChange calls this
        });
    });

    if (streamForm) {
        streamForm.addEventListener('submit', function(e) { // This is the 'startStream' logic
            e.preventDefault();
            const currentStreamName = streamNameInput.value.trim();
            const currentStreamTypeRadio = document.querySelector('input[name="stream_type"]:checked');
            if(!currentStreamTypeRadio) { showAlert('error', 'Form Error', 'Stream type not selected.'); return; }
            const currentStreamType = currentStreamTypeRadio.value;
            
            let formIsValid = true;
            if (!validateStreamName(currentStreamName)) {
                updateValidationState(streamNameInput, false, 'Use letters, numbers, underscores, hyphens. No spaces.');
                formIsValid = false;
            }

            if (currentStreamType === 'rtsp') {
                if (!sourceUrlInput || !validateSourceUrl(sourceUrlInput.value.trim())) {
                     updateValidationState(sourceUrlInput, false, 'Valid RTSP or HTTP(S) URL. e.g., rtsp://...');
                     formIsValid = false;
                }
            } else { 
                const fileSourceTypeRadio = document.querySelector('input[name="file_source_type"]:checked');
                 if(!fileSourceTypeRadio) { showAlert('error', 'Form Error', 'File source type not selected.'); return; }
                const fileSourceType = fileSourceTypeRadio.value;

                if (fileSourceType === 'folder') {
                    if (!videoFileSelect || videoFileSelect.value === '') {
                         updateValidationState(videoFileSelect, false, 'Please select a video file.');
                         formIsValid = false;
                    }
                } else { 
                    if (!videoFilePath || !validateFilePath(videoFilePath.value.trim())) {
                        updateValidationState(videoFilePath, false, 'Please enter a valid file path.');
                        formIsValid = false;
                    }
                }
            }
            
            if (!formIsValid) {
                showAlert('error', 'Validation Error', 'Please correct the fields highlighted in red.');
                return;
            }
            
            const formData = new FormData(streamForm);
            const data = {};
            formData.forEach((value, key) => { data[key] = value; });
            data['hardware_accel'] = document.getElementById('hardware_accel').checked ? 'yes' : 'no';
            
            if (currentStreamType === 'file') {
                data['file_source_type'] = document.querySelector('input[name="file_source_type"]:checked').value;
                 if (data['file_source_type'] === 'folder') {
                    data['video_file'] = videoFileSelect.value; 
                } else { // 'custom'
                    // video_file_path is already in formData, ensure it's trimmed
                    if(data['video_file_path']) data['video_file_path'] = data['video_file_path'].trim();
                }
            }
            
            if (submitButton) {
                submitButton.disabled = true;
                submitButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Starting...';
            }
            
            fetch('/start_stream', { 
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            })
            .then(response => response.json())
            .then(result => {
                if (result.success) {
                    showAlert('success', 'Stream Action', result.message + (result.stream_url ? ` RTSP URL: ${result.stream_url}` : ''));
                    streamForm.reset();
                    
                    if(audioEnabledNo) audioEnabledNo.checked = true;
                    if(audioCodecContainer) audioCodecContainer.style.display = 'none';
                    if(streamTypeFile) streamTypeFile.checked = true;
                    if(fileSourceFolderRadio) fileSourceFolderRadio.checked = true;
                    
                    if(streamTypeFile) streamTypeFile.dispatchEvent(new Event('change')); 
                    else if(streamTypeRtsp) streamTypeRtsp.dispatchEvent(new Event('change')); //This will trigger sub-handler
                   
                    [streamNameInput, sourceUrlInput, videoFileSelect, videoFilePath].forEach(input => {
                        if(input) {
                            input.classList.remove('is-valid', 'is-invalid');
                            const parentNode = input.parentNode;
                            const feedbackDiv = parentNode.querySelector('.invalid-feedback');
                            if (feedbackDiv) feedbackDiv.style.display = 'none';
                        }
                    });
                     checkFormValidityAndUpdateButton(); // Explicitly call after reset and UI updates
                    updateActiveStreams(); 
                } else {
                    showAlert('error', 'Error Starting Stream', result.message || 'Unknown server error. Check backend logs.');
                }
            })
            .catch(error => {
                showAlert('error', 'Network Error', 'Could not connect to server: ' + error);
            })
            .finally(() => {
                if (submitButton) {
                    setTimeout(() => {
                        submitButton.disabled = false;
                        submitButton.innerHTML = 'Start Stream';
                        checkFormValidityAndUpdateButton(); 
                    }, 500);
                }
            });
        });
    }
    
    function initializeCopyButtons() {
        document.querySelectorAll('.copy-btn').forEach(button => {
            const newButton = button.cloneNode(true);
            button.parentNode.replaceChild(newButton, button);

            newButton.addEventListener('click', async () => {
                const streamItem = newButton.closest('.stream-item');
                if (!streamItem) {
                    console.error('Stream item not found');
                    showAlert('error', 'Error', 'Stream item not found.');
                    return;
                }
                
                const streamUrl = streamItem.dataset.streamUrl;
                if (!streamUrl) {
                    console.error('Stream URL not found in dataset:', streamItem.dataset);
                    showAlert('error', 'Error', 'Stream URL not found.');
                    return;
                }

                console.log('Attempting to copy URL:', streamUrl);

                try {
                    // Try modern clipboard API first
                    if (navigator.clipboard && window.isSecureContext) {
                        await navigator.clipboard.writeText(streamUrl);
                        newButton.innerHTML = '<i class="fas fa-check"></i> Copied';
                        newButton.classList.add('copied');
                        console.log('Successfully copied using navigator.clipboard');
                    } else {
                        // Fallback to document.execCommand for older browsers or non-secure contexts
                        const textArea = document.createElement('textarea');
                        textArea.value = streamUrl;
                        textArea.style.position = 'fixed';
                        textArea.style.left = '-999999px';
                        textArea.style.top = '-999999px';
                        document.body.appendChild(textArea);
                        textArea.focus();
                        textArea.select();
                        
                        const successful = document.execCommand('copy');
                        document.body.removeChild(textArea);
                        
                        if (successful) {
                            newButton.innerHTML = '<i class="fas fa-check"></i> Copied';
                            newButton.classList.add('copied');
                            console.log('Successfully copied using execCommand');
                        } else {
                            throw new Error('execCommand copy failed');
                        }
                    }
                    
                    // Reset button after 2 seconds
                    setTimeout(() => {
                        newButton.innerHTML = '<i class="fas fa-copy"></i> Copy URL';
                        newButton.classList.remove('copied');
                    }, 2000);
                    
                } catch (err) {
                    console.error('Failed to copy text:', err);
                    showAlert('error', 'Copy Failed', `Failed to copy URL: ${err.message}`);
                }
            });
        });
    }

    function initializeViewButtons() {
        document.querySelectorAll('.view-btn').forEach(button => {
            const newButton = button.cloneNode(true);
            button.parentNode.replaceChild(newButton, button);

            newButton.addEventListener('click', function() {
                const streamItem = newButton.closest('.stream-item');
                if (!streamItem) {
                    console.error('Stream item not found');
                    showAlert('error', 'Error', 'Stream item not found.');
                    return;
                }
                
                const streamName = streamItem.dataset.streamName;
                if (!streamName) {
                    console.error('Stream name not found in dataset:', streamItem.dataset);
                    showAlert('error', 'Error', 'Stream name not found.');
                    return;
                }

                // Open stream viewer in new tab
                const viewerUrl = `/stream/${streamName}/view`;
                window.open(viewerUrl, '_blank');
            });
        });
    }

    function initializeDeleteButtons() {
        document.querySelectorAll('.delete-btn').forEach(button => {
            const newButton = button.cloneNode(true);
            button.parentNode.replaceChild(newButton, button);
            
            newButton.addEventListener('click', async () => {
                const streamItem = newButton.closest('.stream-item');
                 if (!streamItem) return;
                const streamName = streamItem.dataset.streamName; 
                 if (!streamName) {
                    return;
                }
                
                if (confirm(`Are you sure you want to stop the stream "${streamName}"?`)) {
                    newButton.disabled = true;
                    newButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Stopping...';
                    
                    try {
                        const response = await fetch('/stop_stream', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json', },
                            body: JSON.stringify({ stream_name: streamName })
                        });
                        const data = await response.json();
                        if (response.ok && data.success) {
                            showAlert('success', 'Success', `Stream "${streamName}" stopped successfully`);
                            updateActiveStreams(); 
                        } else {
                            throw new Error(data.message || 'Failed to stop stream');
                        }
                    } catch (err) {
                        showAlert('error', 'Error Stopping Stream', err.message);
                        newButton.disabled = false; 
                        newButton.innerHTML = '<i class="fas fa-stop-circle"></i> Stop Stream';
                    }
                }
            });
        });
    }
    
    function initializeErrorLogButtons() {
        document.querySelectorAll('.view-log-btn').forEach(button => {
            const newButton = button.cloneNode(true);
            button.parentNode.replaceChild(newButton, button);

            newButton.addEventListener('click', function() {
                const streamName = this.dataset.streamName;
                const logType = this.dataset.logType;
                if (streamName && logType) {
                    window.open(`/view_log/${logType}/${streamName}`, '_blank');
                }
            });
        });
    }

    function updateActiveStreams() {
        const activeStreamsContainer = document.getElementById('activeStreams');
        if (!activeStreamsContainer) return;

        fetch('/get_active_streams')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    activeStreamsContainer.innerHTML = ''; // Clear previous streams
                    if (data.streams && data.streams.length > 0) {
                        data.streams.forEach(stream => {
                            const cfg = stream.config || {};
                            const name = stream.name || 'N/A';
                            let statusClass = 'status-stopped';
                            if (stream.status === 'running') statusClass = 'status-active';
                            else if (stream.status === 'error' || stream.has_error) statusClass = 'status-error';
                            else if (stream.status === 'starting') statusClass = 'status-starting';

                            const statusText = stream.status ? stream.status.toUpperCase() : 'UNKNOWN';
                            const errorMsg = stream.error || '';
                            const hasError = stream.has_error || false;
                            const crashLogPath = stream.crash_log_path;
                            const streamUrl = stream.url || '';

                            const itemHTML = `
                                <div class="stream-item ${hasError ? 'has-error' : ''}" data-stream-name="${name}" data-stream-url="${streamUrl}">
                                    <div class="stream-header">
                                        <h5 class="stream-name">${name}</h5>
                                        <span class="elapsed-badge"><i class="far fa-clock"></i> ${stream.elapsed_time || 'N/A'}</span>
                                    </div>
                                    <div class="stream-url-display">
                                        <small>URL: ${streamUrl}</small>
                                        ${cfg.stream_type === 'file' && stream.file_info ? `<small class="file-info-inline"> | File: ${stream.file_info}</small>` : ''}
                                        ${cfg.stream_type === 'rtsp' && cfg.source_url ? `<small class="file-info-inline"> | Source: ${cfg.source_url}</small>` : ''}
                                    </div>
                                    <div class="stream-badges-and-controls">
                                        <div class="stream-badges">
                                            <span class="stream-badge codec-badge">${stream.codec || 'N/A'}</span>
                                            <span class="stream-badge audio-badge">${stream.audio || 'N/A'}</span>
                                            <span class="stream-badge resolution-badge">${stream.resolution || 'N/A'}p</span>
                                            <span class="stream-badge fps-badge">FPS ${stream.fps || 'N/A'}</span>
                                            <span class="stream-badge accel-badge accel-${(stream.accel_type || 'cpu').toLowerCase()}">${stream.accel_type ? stream.accel_type.toUpperCase() : 'CPU'}</span>
                                            <span class="stream-badge status-badge ${statusClass}">${statusText}</span>
                                            ${stream.remaining_time && stream.remaining_time !== 'Expired' && stream.remaining_time !== 'Unlimited' ? `<span class="duration-badge">${stream.remaining_time}</span>` : ''}
                                            ${stream.remaining_time === 'Unlimited' ? `<span class="unlimited-badge">Unlimited</span>` : ''}
                                            ${stream.remaining_time === 'Expired' ? `<span class="duration-badge expired">Expired</span>` : ''}
                                        </div>
                                        <div class="stream-controls">
                                            <button class="btn btn-sm btn-outline-secondary copy-btn" title="Copy RTSP URL"><i class="fas fa-copy"></i> Copy URL</button>
                                            <button class="btn btn-sm btn-outline-primary view-btn" title="View Stream in Browser"><i class="fas fa-play-circle"></i> View Stream</button>
                                            <button class="btn btn-sm btn-danger delete-btn" title="Stop Stream"><i class="fas fa-stop-circle"></i> Stop Stream</button>
                                        </div>
                                    </div>
                                    ${hasError ? `
                                        <div class="error-display">
                                            <p class="error-message"><strong>Error:</strong> ${errorMsg}</p>
                                            ${crashLogPath ? `<button class="btn btn-sm btn-outline-warning view-log-btn" data-stream-name="${name}" data-log-type="crash">View Crash Log</button>` : ''}
                                            <button class="btn btn-sm btn-outline-info view-log-btn" data-stream-name="${name}" data-log-type="main">View Main Log</button>
                                            <button class="btn btn-sm btn-outline-secondary view-log-btn" data-stream-name="${name}" data-log-type="err">View FFmpeg Log</button>
                                        </div>
                                    ` : ''}
                                </div>`;
                            activeStreamsContainer.innerHTML += itemHTML;
                        });
                    } else {
                        activeStreamsContainer.innerHTML = '<div class="p-3 mb-2 bg-light text-dark rounded-3 text-center">No active streams.</div>';
                    }
                    initializeCopyButtons();
                    initializeViewButtons();
                    initializeDeleteButtons();
                    initializeErrorLogButtons(); 
                } else {
                    activeStreamsContainer.innerHTML = '<p class="text-danger">Error loading streams: ' + (data.message || '') + '</p>';
                }
            })
            .catch(error => {
                activeStreamsContainer.innerHTML = '<p class="text-danger">Failed to fetch streams. Check connection.</p>';
            });
    }

    checkFormValidityAndUpdateButton();
    loadVideoFiles();
    updateActiveStreams();
    setInterval(updateActiveStreams, 7000);
    checkMediaMTXStatus();
    setInterval(checkMediaMTXStatus, 10000);

    // Start MediaMTX status check
    checkMediaMTXStatus();

    // Initialize cleanup button
    initializeCleanupButton();

    // --- Cleanup Functionality ---
    function initializeCleanupButton() {
        const cleanupBtn = document.getElementById('cleanupStaleStreamsBtn');
        if (cleanupBtn) {
            cleanupBtn.addEventListener('click', async () => {
                if (confirm('Clean up stale error streams? This will remove streams with error status that are no longer active.')) {
                    cleanupBtn.disabled = true;
                    cleanupBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Cleaning...';
                    
                    try {
                        const response = await fetch('/cleanup_stale_streams', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' }
                        });
                        const data = await response.json();
                        
                        if (response.ok && data.success) {
                            showAlert('success', 'Cleanup Complete', data.message);
                            updateActiveStreams(); // Refresh the streams list
                        } else {
                            throw new Error(data.message || 'Failed to cleanup streams');
                        }
                    } catch (err) {
                        showAlert('error', 'Cleanup Failed', err.message);
                    } finally {
                        cleanupBtn.disabled = false;
                        cleanupBtn.innerHTML = '<i class="fas fa-broom"></i> Cleanup';
                    }
                }
            });
        }
    }

    // --- Video Info Fetching Logic ---
    // Function to fetch video info from the backend
    async function fetchVideoInfo(filePath) {
        console.log('[fetchVideoInfo] Called with filePath:', filePath);
        const videoDetailsContainer = document.getElementById('video_details_container');
        const videoMetadataDisplay = document.getElementById('video_metadata_display');

        if (!filePath) {
            console.log('[fetchVideoInfo] filePath is empty, hiding details.');
            if (videoDetailsContainer) videoDetailsContainer.style.display = 'none';
            if (videoMetadataDisplay) videoMetadataDisplay.textContent = '';
            return;
        }

        if (videoMetadataDisplay) videoMetadataDisplay.textContent = 'Loading video details...';
        if (videoDetailsContainer) videoDetailsContainer.style.display = 'block';
        console.log('[fetchVideoInfo] Set to loading, container display: block');

        try {
            console.log('[fetchVideoInfo] Attempting fetch to /get_video_info');
            const response = await fetch('/get_video_info', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ file_path: filePath }),
            });
            console.log('[fetchVideoInfo] Fetch response received:', response.status);
            if (!response.ok) {
                const errorData = await response.json();
                console.error('[fetchVideoInfo] Response not OK:', errorData);
                throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            console.log('[fetchVideoInfo] Fetch data parsed:', data);
            if (data.success) {
                updateVideoDetailsDisplay(data.details);
            } else {
                updateVideoDetailsDisplay({ error: data.error || 'Could not retrieve video details.' });
            }
        } catch (error) {
            console.error('[fetchVideoInfo] Catch block error:', error);
            updateVideoDetailsDisplay({ error: `Error: ${error.message}` });
        }
    }

    // Function to update the video details display
    function updateVideoDetailsDisplay(details) {
        console.log('[updateVideoDetailsDisplay] Called with details:', details);
        const videoMetadataDisplay = document.getElementById('video_metadata_display');
        const videoDetailsContainer = document.getElementById('video_details_container');

        if (!videoMetadataDisplay || !videoDetailsContainer) {
            console.error('[updateVideoDetailsDisplay] CRITICAL: display elements not found.');
            return;
        }

        if (details && details.error) {
            videoMetadataDisplay.innerHTML = `<span class="text-danger">${details.error}</span>`;
        } else if (details && details.fps) {
            videoMetadataDisplay.innerHTML = 
                '<strong>FPS:</strong> ' + details.fps + '<br>' +
                '<strong>Codec:</strong> ' + (details.codec_long_name || 'N/A') + ' (' + details.codec_tag_string + ')<br>' +
                '<strong>Resolution:</strong> ' + details.width + 'x' + details.height;
        } else {
            videoMetadataDisplay.textContent = 'Could not retrieve video details or file is invalid.';
        }
        videoDetailsContainer.style.display = 'block';
        console.log('[updateVideoDetailsDisplay] Container display: block, content set.');
    }

    // Get references to elements again within this scope if not already global or passed
    const videoFileSelectForInfo = document.getElementById('video_file');
    const videoFilePathInputForInfo = document.getElementById('video_file_path');
    const videoDetailsContainerForInfo = document.getElementById('video_details_container');

    if (videoDetailsContainerForInfo) {
        console.log('[DOMContentLoaded - VideoInfoSetup] video_details_container found.');
    } else {
        console.error('[DOMContentLoaded - VideoInfoSetup] CRITICAL: video_details_container NOT found.');
    }

    if (videoFileSelectForInfo) {
        console.log('[DOMContentLoaded - VideoInfoSetup] videoFileSelect element found. Attaching listener.');
        videoFileSelectForInfo.addEventListener('change', function() {
            console.log('[videoFileSelect change - VideoInfoSetup] Event fired. Value:', this.value);
            if (this.value) {
                fetchVideoInfo(this.value);
            } else {
                if (videoDetailsContainerForInfo) videoDetailsContainerForInfo.style.display = 'none';
                console.log('[videoFileSelect change - VideoInfoSetup] No value, hiding details container.');
            }
        });
    } else {
        console.error('[DOMContentLoaded - VideoInfoSetup] videoFileSelect element NOT found.');
    }

    if (videoFilePathInputForInfo) {
        console.log('[DOMContentLoaded - VideoInfoSetup] videoFilePathInput element found. Attaching listeners.');
        videoFilePathInputForInfo.addEventListener('blur', function() { 
            console.log('[videoFilePathInput blur - VideoInfoSetup] Event fired. Value:', this.value);
            if (this.value) {
                fetchVideoInfo(this.value);
            } else {
                 if (videoDetailsContainerForInfo) videoDetailsContainerForInfo.style.display = 'none';
                 console.log('[videoFilePathInput blur - VideoInfoSetup] No value, hiding details container.');
            }
        });
        videoFilePathInputForInfo.addEventListener('keypress', function(event) {
            if (event.key === 'Enter') {
                console.log('[videoFilePathInput keypress Enter - VideoInfoSetup] Event fired. Value:', this.value);
                event.preventDefault(); 
                 if (this.value) {
                    fetchVideoInfo(this.value);
                } else {
                    if (videoDetailsContainerForInfo) videoDetailsContainerForInfo.style.display = 'none';
                    console.log('[videoFilePathInput keypress Enter - VideoInfoSetup] No value, hiding details container.');
                }
            }
        });
    } else {
        console.error('[DOMContentLoaded - VideoInfoSetup] videoFilePathInput element NOT found.');
    }
    console.log('[DOMContentLoaded - VideoInfoSetup] Event listeners for video info setup complete.');
    // --- End Video Info Fetching Logic ---

});

function toggleLegend() {
    const legendContent = document.getElementById('legendContent');
    if (!legendContent) return;
    legendContent.style.display = legendContent.style.display === 'block' ? 'none' : 'block';
}

async function checkMediaMTXStatus() {
    try {
        const response = await fetch('/mediamtx/status');
        const data = await response.json();
        
        const statusText = document.getElementById('mediamtx-status-text');
        const restartBtn = document.getElementById('mediamtx-restart-btn');
        const logLink = document.getElementById('mediamtx-log-link');
        const statusDiv = document.getElementById('mediamtx-status');
        
        if (!statusText || !restartBtn || !logLink || !statusDiv) {
            return;
        }

        if (data.success) {
            if (data.running) {
                statusText.textContent = `Running (PID: ${data.pid || 'Unknown'})`;
                statusText.className = 'status-text status-running';
                statusDiv.className = 'mediamtx-status status-ok';
                restartBtn.style.display = 'inline-block';
                restartBtn.textContent = 'Restart';
            } else {
                statusText.textContent = 'Not Running';
                statusText.className = 'status-text status-stopped';
                statusDiv.className = 'mediamtx-status status-error';
                restartBtn.style.display = 'inline-block';
                restartBtn.textContent = 'Start';
            }
            logLink.style.display = data.log_exists ? 'inline-block' : 'none';
        } else {
            statusText.textContent = 'Error';
            statusText.className = 'status-text status-error';
             showAlert('error', 'MediaMTX Status Error', data.message || "Could not get MediaMTX status.");
        }
    } catch (error) {
        /* console.error('Error checking MediaMTX status:', error); */
        const statusText = document.getElementById('mediamtx-status-text');
        if(statusText) {
            statusText.textContent = 'Error checking status';
            statusText.className = 'status-text status-error';
        }
    }
}

async function restartMediaMTX() {
    const restartBtn = document.getElementById('mediamtx-restart-btn');
    const statusText = document.getElementById('mediamtx-status-text');
    
    if(!restartBtn || !statusText) return;

    const originalButtonText = restartBtn.textContent;
    restartBtn.disabled = true;
    restartBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
    statusText.textContent = 'Processing...';
    
    try {
        const response = await fetch('/mediamtx/restart', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();
        if (data.success) {
            showAlert('success', 'MediaMTX Action', data.message || 'MediaMTX command sent.');
        } else {
            showAlert('error', 'MediaMTX Action Failed', data.message || 'Unknown error during MediaMTX operation.');
        }
    } catch (error) {
        /* console.error('Error with MediaMTX action:', error); */
        showAlert('error', 'Network Error', 'Could not connect to server for MediaMTX action.');
    } finally {
        restartBtn.disabled = false;
        restartBtn.innerHTML = originalButtonText; 
        setTimeout(checkMediaMTXStatus, 2000); 
    }
}
