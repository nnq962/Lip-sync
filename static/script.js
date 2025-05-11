document.addEventListener('DOMContentLoaded', function() {
    // API URL - Thay đổi thành URL của API mới
    const API_URL = 'http://localhost:8000/api/generate-viseme';
    
    // Các phần tử DOM
    const avatar = document.getElementById('avatar');
    const audioFileInput = document.getElementById('audio-file');
    const transcriptText = document.getElementById('transcript-text');
    const audioFileName = document.getElementById('audio-file-name');
    const processButton = document.getElementById('process-button');
    const playButton = document.getElementById('play-button');
    const progressBar = document.getElementById('progress-bar');
    const statusMessage = document.getElementById('status-message');
    const avatarContainer = document.querySelector('.avatar-container');
    
    // Đường dẫn đến các ảnh khẩu hình (dựa trên tên file thực tế)
    const avatarImages = {
        'default': '../static/images/avatar.png',            // Mặc định - miệng đóng
        'A.E.I': '../static/images/A.E.I.png',               // A, E, I
        'B.M.P': '../static/images/B.M.P.png',               // B, M, P
        'C.D.N.S.T.X.Y.Z': '../static/images/C.D.N.S.T.X.Y.Z.png', // C, D, N, S, T, X, Y, Z
        'CH.J.SH': '../static/images/CH.J.SH.png',           // CH, J, SH
        'EE': '../static/images/EE.png',                     // EE
        'F.V': '../static/images/F.V.png',                   // F, V
        'G.K': '../static/images/G.K.png',                   // G, K
        'L': '../static/images/L.png',                       // L
        'O': '../static/images/O.png',                       // O
        'TH': '../static/images/TH.png',                     // TH
        'U': '../static/images/U.png',                       // U
        'W.Q': '../static/images/W.Q.png'                    // W, Q
    };
    
    // Ánh xạ từ Viseme ID (0-17) sang avatar images
    const visemeToAvatarMap = {
        0: 'default',            // Rest/Neutral -> Mặc định
        1: 'B.M.P',              // M/B/P -> B.M.P
        2: 'F.V',                // F/V -> F.V
        3: 'C.D.N.S.T.X.Y.Z',    // T/D -> C.D.N.S.T.X.Y.Z
        4: 'C.D.N.S.T.X.Y.Z',    // N -> C.D.N.S.T.X.Y.Z
        5: 'G.K',                // K/G -> G.K
        6: 'CH.J.SH',            // CH/J/SH -> CH.J.SH
        7: 'C.D.N.S.T.X.Y.Z',    // S/Z -> C.D.N.S.T.X.Y.Z
        8: 'TH',                 // TH -> TH
        9: 'L',                  // L -> L
        10: 'L',                 // R -> L (không có ảnh riêng cho R, dùng L thay thế)
        11: 'W.Q',               // W/J -> W.Q
        12: 'A.E.I',             // A -> A.E.I
        13: 'A.E.I',             // E -> A.E.I
        14: 'EE',                // I -> EE
        15: 'O',                 // O/Ə -> O
        16: 'U',                 // U -> U
        17: 'A.E.I'              // Diphthongs -> A.E.I (không có ảnh riêng cho nguyên âm đôi)
    };
    
    // Biến lưu trữ dữ liệu
    let audioFile = null;
    let visemeData = null;
    let audioElement = new Audio();
    let isPlaying = false;
    let requestAnimationFrameId = null;
    let lastVisemeIndex = -1;
    let preloadedImages = {};
    
    // Hàm kiểm tra xem có thể xử lý được không
    function checkProcessEnabled() {
        const hasAudio = audioFile !== null;
        const hasText = transcriptText.value.trim() !== '';
        processButton.disabled = !(hasAudio && hasText);
    }
    
    // Hàm kiểm tra xem có thể phát được không
    function checkPlayEnabled() {
        playButton.disabled = !(visemeData && audioFile);
    }
    
    // Lắng nghe sự kiện thay đổi file âm thanh
    audioFileInput.addEventListener('change', function(event) {
        if (event.target.files.length > 0) {
            audioFile = event.target.files[0];
            audioFileName.textContent = audioFile.name;
            
            // Đặt lại trạng thái phát nếu file đã thay đổi
            if (isPlaying) {
                stopPlayback();
            }
            
            // Tạo URL cho file âm thanh
            if (audioElement.src) {
                URL.revokeObjectURL(audioElement.src);
            }
            audioElement.src = URL.createObjectURL(audioFile);
            
            // Đặt lại visemeData khi thay đổi file âm thanh
            visemeData = null;
            playButton.disabled = true;
            
            // Xóa thông báo
            statusMessage.textContent = "";
            statusMessage.className = "status-message";
            
            // Kiểm tra xem có thể xử lý được không
            checkProcessEnabled();
        } else {
            audioFile = null;
            audioFileName.textContent = "Chưa chọn file...";
            playButton.disabled = true;
            statusMessage.textContent = "";
            statusMessage.className = "status-message";
            checkProcessEnabled();
        }
    });
    
    // Lắng nghe sự kiện nhập văn bản
    transcriptText.addEventListener('input', function() {
        checkProcessEnabled();
    });
    
    // Lắng nghe sự kiện nhấn nút Xử lý
    processButton.addEventListener('click', function() {
        if (!audioFile || transcriptText.value.trim() === '') {
            return;
        }
        
        // Đặt lại trạng thái phát nếu đang phát
        if (isPlaying) {
            stopPlayback();
        }
        
        // Hiển thị trạng thái đang xử lý
        statusMessage.textContent = "Đang xử lý";
        statusMessage.className = "status-message loading";
        processButton.disabled = true;
        
        // Tạo form data để gửi lên API
        const formData = new FormData();
        formData.append('audio_file', audioFile);
        formData.append('transcript', transcriptText.value.trim());
        
        // Gọi API
        fetch(API_URL, {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`Lỗi ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            // Lưu dữ liệu viseme
            visemeData = data;
            
            // Log để kiểm tra dữ liệu viseme
            console.log("Dữ liệu viseme:", visemeData);
            
            // Gộp thông báo thành công và thời gian xử lý
            let successMessage = `Xử lý thành công! (${visemeData.viseme_timeline.length} viseme, ${visemeData.metadata.total_duration.toFixed(2)}s)`;
            if (visemeData.processing_time) {
                successMessage += ` Thời gian xử lý: ${visemeData.processing_time.toFixed(3)}s`;
            }
            
            // Hiển thị thông báo thành công
            statusMessage.textContent = successMessage;
            statusMessage.className = "status-message success";
            
            // Cho phép phát
            playButton.disabled = false;
            
            // Cho phép xử lý lại
            processButton.disabled = false;
            
            // Preload các ảnh
            preloadAllImages();
        })
        .catch(error => {
            console.error("API Error:", error);
            
            // Hiển thị thông báo lỗi
            statusMessage.textContent = `Lỗi: ${error.message}`;
            statusMessage.className = "status-message error";
            
            // Cho phép thử lại
            processButton.disabled = false;
        });
    });
    
    // Lắng nghe sự kiện nhấn nút Phát
    playButton.addEventListener('click', function() {
        if (!visemeData || !audioFile) {
            return;
        }
        
        if (isPlaying) {
            stopPlayback();
        } else {
            startPlayback();
        }
    });
    
    // Hàm bắt đầu phát
    function startPlayback() {
        if (isPlaying) return;
        
        isPlaying = true;
        playButton.textContent = "Dừng";
        
        // Đặt lại avatar về trạng thái mặc định
        avatar.src = avatarImages['default'];
        lastVisemeIndex = -1;
        
        // Đặt lại progress bar
        progressBar.style.width = "0%";
        
        // Lắng nghe sự kiện kết thúc audio
        audioElement.onended = stopPlayback;
        
        // Lắng nghe sự kiện thời gian thay đổi để cập nhật progress bar
        audioElement.ontimeupdate = function() {
            const progressPercent = (audioElement.currentTime / audioElement.duration) * 100;
            progressBar.style.width = `${progressPercent}%`;
        };
        
        // Bắt đầu phát audio
        audioElement.currentTime = 0;
        audioElement.play().catch(error => {
            console.error("Lỗi khi phát audio:", error);
            stopPlayback();
        });
        
        // Bắt đầu animation loop
        startAnimationLoop();
    }
    
    // Hàm dừng phát
    function stopPlayback() {
        if (!isPlaying) return;
        
        isPlaying = false;
        
        playButton.textContent = "Phát";
        
        // Dừng animation loop
        if (requestAnimationFrameId) {
            cancelAnimationFrame(requestAnimationFrameId);
            requestAnimationFrameId = null;
        }
        
        // Dừng audio
        audioElement.pause();
        
        // Đặt lại avatar về trạng thái mặc định
        avatar.src = avatarImages['default'];
        lastVisemeIndex = -1;
    }
    
    // Hàm bắt đầu animation loop
    function startAnimationLoop() {
        const visemeTimeline = visemeData.viseme_timeline;
        const startTime = Date.now();
        
        function animate() {
            if (!isPlaying) return;
            
            const currentTime = audioElement.currentTime;
            let currentVisemeIndex = -1;
            
            // Tìm viseme phù hợp với thời điểm hiện tại
            for (let i = 0; i < visemeTimeline.length; i++) {
                const viseme = visemeTimeline[i];
                if (currentTime >= viseme.start && currentTime <= viseme.end) {
                    currentVisemeIndex = i;
                    break;
                }
                
                // Nếu đã vượt qua thời điểm hiện tại
                if (currentTime < viseme.start) {
                    // Lấy viseme trước đó
                    if (i > 0) {
                        currentVisemeIndex = i - 1;
                    }
                    break;
                }
            }
            
            // Nếu không tìm thấy viseme phù hợp và đã qua hết tất cả các viseme
            if (currentVisemeIndex === -1 && visemeTimeline.length > 0 && currentTime > visemeTimeline[visemeTimeline.length - 1].end) {
                currentVisemeIndex = visemeTimeline.length - 1;
            }
            
            // Cập nhật khẩu hình nếu có sự thay đổi
            if (currentVisemeIndex !== -1 && currentVisemeIndex !== lastVisemeIndex) {
                updateAvatarImage(visemeTimeline[currentVisemeIndex]);
                lastVisemeIndex = currentVisemeIndex;
            }
            
            // Tiếp tục animation loop
            requestAnimationFrameId = requestAnimationFrame(animate);
        }
        
        // Bắt đầu animation loop
        animate();
    }
    
    // Hàm cập nhật ảnh avatar dựa trên viseme ID
    function updateAvatarImage(visemeObj) {
        // Lấy viseme ID từ API mới
        const visemeId = visemeObj.viseme;
        
        // Ánh xạ từ viseme ID sang hình ảnh avatar
        const imageKey = visemeToAvatarMap[visemeId] || 'default';
        
        // Cập nhật ảnh avatar
        if (preloadedImages[imageKey]) {
            avatar.src = preloadedImages[imageKey].src;
        } else {
            avatar.src = avatarImages[imageKey];
        }
        
        // Log để debug
        console.log(`Phoneme: ${visemeObj.phoneme}, Viseme ID: ${visemeId}, ImageKey: ${imageKey}`);
    }
    
    // Hàm preload tất cả các ảnh
    function preloadAllImages() {
        for (const key in avatarImages) {
            if (!preloadedImages[key]) {
                preloadedImages[key] = new Image();
                preloadedImages[key].src = avatarImages[key];
            }
        }
    }
    
    // Preload ảnh mặc định ngay khi trang tải
    (function() {
        preloadedImages['default'] = new Image();
        preloadedImages['default'].src = avatarImages['default'];
    })();
    
    // Reset UI khi trang mới tải
    audioFileName.textContent = "Chưa chọn file...";
    processButton.disabled = true;
    playButton.disabled = true;
    progressBar.style.width = "0%";
    statusMessage.textContent = "";
    statusMessage.className = "status-message";
});