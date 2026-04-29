// Navigation Logic
const navBtns = document.querySelectorAll('.nav-btn');
const views = document.querySelectorAll('.view-section');

navBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        navBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const viewId = btn.getAttribute('data-view');
        
        views.forEach(v => v.style.display = 'none');
        document.getElementById(viewId).style.display = 'flex';

        if (viewId === 'progress-view') {
            loadProgress();
        }
        
        if (viewId === 'maps-view' && map) {
            // Leaflet needs to know the container size changed
            setTimeout(() => map.invalidateSize(), 100);
        }
    });
});

// GeoGraph Interactive Map Logic
let map = null;
let markers = [];
let routeLayer = null;
let mapChart = null;

function initMap() {
    if (map) return;
    
    // Default center (London)
    map = L.map('interactive-map').setView([51.505, -0.09], 13);
    
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);

    // Try to get user location
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition((position) => {
            const { latitude, longitude } = position.coords;
            map.setView([latitude, longitude], 13);
            L.marker([latitude, longitude]).addTo(map)
                .bindPopup('You are here')
                .openPopup();
        });
    }
}

// Call init when browser finishes loading
window.addEventListener('DOMContentLoaded', initMap);

// Helper for UI loading states
function showLoading(elementId) {
    document.getElementById(elementId).innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Processing...';
    document.getElementById(elementId).style.display = 'block';
}

async function parseApiResponse(res) {
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
        throw new Error(data.detail || `Request failed with status ${res.status}`);
    }
    return data;
}

// 1. Doubt Solver & Image Question (Chat)
const chatForm = document.getElementById('chat-form');
const chatMessages = document.getElementById('chat-messages');
const userInput = document.getElementById('user-input');
const fileUpload = document.getElementById('file-upload');
const filePreview = document.getElementById('file-preview-container');
const fileNameDisplay = document.getElementById('file-name');
const clearFileBtn = document.getElementById('clear-file');

let chatHistory = [];

fileUpload.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        fileNameDisplay.textContent = e.target.files[0].name;
        filePreview.style.display = 'flex';
    }
});

clearFileBtn.addEventListener('click', () => {
    fileUpload.value = '';
    filePreview.style.display = 'none';
});

function appendMessage(role, content) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}-message`;
    msgDiv.innerHTML = role === 'ai' ? marked.parse(content) : content;
    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

let activeChart = null;

chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = userInput.value.trim();
    const file = fileUpload.files[0];
    
    if (!text && !file) return;

    let displayMsg = text;
    if (file) displayMsg = text ? `[Image attached] ${text}` : `[Image uploaded]`;
    
    appendMessage('user', displayMsg);
    
    const formData = new FormData();
    formData.append('message', text || 'Analyze this image');
    formData.append('agent_type', 'auto');
    formData.append('history', JSON.stringify(chatHistory));
    if (file) formData.append('file', file);

    userInput.value = '';
    fileUpload.value = '';
    filePreview.style.display = 'none';
    
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'message ai-message';
    loadingDiv.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Thinking...';
    loadingDiv.id = 'typing-' + Date.now();
    chatMessages.appendChild(loadingDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    try {
        const res = await fetch('/api/chat', { method: 'POST', body: formData });
        const data = await parseApiResponse(res);
        
        const loader = document.getElementById(loadingDiv.id);
        if(loader) loader.remove();
        
        if (data.status === 'success') {
            let msgContent = marked.parse(data.response);
            
            if (data.graph_data) {
                const canvasId = 'chart-' + Date.now();
                msgContent += `<div class="graph-container"><canvas id="${canvasId}"></canvas></div>`;
                appendMessage('ai', msgContent);
                
                setTimeout(() => {
                    const ctx = document.getElementById(canvasId).getContext('2d');
                    if (activeChart) activeChart.destroy();
                    
                    const chartConfig = {
                        type: 'bar',
                        data: {
                            labels: data.graph_data.labels,
                            datasets: [{
                                label: data.graph_data.title,
                                data: data.graph_data.data,
                                backgroundColor: 'rgba(99, 102, 241, 0.5)', /* Primary indigo */
                                borderColor: 'rgba(99, 102, 241, 1)',
                                borderWidth: 1
                            }]
                        },
                        options: {
                            responsive: true,
                            plugins: {
                                legend: { labels: { color: '#1e293b' } },
                                title: { display: true, text: data.graph_data.title, color: '#1e293b' }
                            },
                            scales: {
                                y: { ticks: { color: '#64748b' }, grid: { color: 'rgba(0,0,0,0.05)' } },
                                x: { ticks: { color: '#64748b' }, grid: { color: 'rgba(0,0,0,0.05)' } }
                            }
                        }
                    };
                    
                    if (data.graph_data.type === 'directions') {
                        chartConfig.data.datasets[0].backgroundColor = ['rgba(99, 102, 241, 0.5)', 'rgba(56, 189, 248, 0.5)'];
                        chartConfig.data.datasets[0].borderColor = ['rgba(99, 102, 241, 1)', 'rgba(56, 189, 248, 1)'];
                    }
                    
                    activeChart = new Chart(ctx, chartConfig);
                }, 100);
            } else {
                appendMessage('ai', msgContent);
            }
            
            speakText(data.response); // Trigger Voice Assistant
            
            chatHistory.push({role: 'user', content: displayMsg});
            chatHistory.push({role: 'ai', content: data.response});
            document.getElementById('active-agent-badge').innerHTML = `<span class="pulse"></span> ${data.agent_used.toUpperCase()}`;
        } else {
            appendMessage('ai', 'Error: ' + data.detail);
        }
    } catch (err) {
        const loader = document.getElementById(loadingDiv.id);
        if(loader) loader.remove();
        appendMessage('ai', `Upload failed: ${err.message}`);
    }
});

async function downloadPDF(text) {
    if (!text.trim()) {
        alert("Nothing to export!");
        return;
    }
    try {
        const response = await fetch('/api/pdf/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: text })
        });
        if (!response.ok) throw new Error("PDF generation failed");
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'AI_Life_Dashboard_Export.pdf';
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
    } catch (error) {
        alert("Error exporting PDF: " + error.message);
    }
}

const exportChatBtn = document.getElementById('export-chat-btn');
if (exportChatBtn) {
    exportChatBtn.addEventListener('click', () => {
        const aiMessages = document.querySelectorAll('.ai-message');
        if (aiMessages.length === 0) return;
        let chatText = "# AI Life Dashboard - Chat Log\n\n";
        aiMessages.forEach((msg, idx) => {
            if (msg.id && msg.id.startsWith('typing')) return;
            const textContent = msg.innerText.replace(/Thinking.../g, '').trim();
            if (textContent) chatText += `## Interaction ${idx}\n${textContent}\n\n`;
        });
        downloadPDF(chatText);
    });
}

const exportNotesBtn = document.getElementById('export-notes-btn');
if (exportNotesBtn) {
    exportNotesBtn.addEventListener('click', () => {
        const notesResult = document.getElementById('notes-result').innerText;
        downloadPDF(notesResult);
    });
}

// 2. Quiz Generator
const generateQuizBtn = document.getElementById('generate-quiz-btn');
const quizContainer = document.getElementById('quiz-container');
let currentQuizData = null;
let currentQuizTopic = "";

generateQuizBtn.addEventListener('click', async () => {
    const topic = document.getElementById('quiz-topic').value;
    if (!topic) return;
    
    generateQuizBtn.disabled = true;
    generateQuizBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
    
    try {
        const res = await fetch('/api/quiz', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({topic})
        });
        const data = await res.json();
        
        if (data.status === 'success') {
            currentQuizData = data.quiz;
            currentQuizTopic = topic;
            renderQuiz();
        }
    } catch (e) {
        alert("Failed to generate quiz");
    } finally {
        generateQuizBtn.disabled = false;
        generateQuizBtn.innerHTML = 'Generate';
    }
});

function renderQuiz() {
    quizContainer.style.display = 'block';
    quizContainer.innerHTML = '';
    
    currentQuizData.forEach((q, i) => {
        let html = `<div class="quiz-q" id="q${i}"><h3>${i+1}. ${q.question}</h3>`;
        q.options.forEach(opt => {
            html += `<label class="quiz-opt"><input type="radio" name="q${i}" value="${opt}"> ${opt}</label>`;
        });
        html += `</div>`;
        quizContainer.innerHTML += html;
    });
    
    quizContainer.innerHTML += `<button id="submit-quiz" class="primary-btn">Submit Answers</button><div id="quiz-result" style="margin-top:1rem; font-weight:bold;"></div>`;
    
    document.getElementById('submit-quiz').addEventListener('click', evaluateQuiz);
}

async function evaluateQuiz() {
    let score = 0;
    currentQuizData.forEach((q, i) => {
        const selected = document.querySelector(`input[name="q${i}"]:checked`);
        const qDiv = document.getElementById(`q${i}`);
        if (selected && selected.value === q.correct_answer) {
            score++;
            qDiv.style.border = "2px solid #10b981";
        } else {
            qDiv.style.border = "2px solid #ef4444";
            const exp = document.createElement('div');
            exp.style.color = "#ef4444";
            exp.style.marginTop = "10px";
            exp.innerHTML = `<strong>Correct Answer:</strong> ${q.correct_answer}<br><em>${q.explanation}</em>`;
            qDiv.appendChild(exp);
        }
    });
    
    const resDiv = document.getElementById('quiz-result');
    resDiv.textContent = `You scored ${score} out of ${currentQuizData.length}!`;
    document.getElementById('submit-quiz').style.display = 'none';

    // Submit to DB
    await fetch('/api/quiz/submit', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            user_id: "demo_user",
            topic: currentQuizTopic,
            score: score,
            total: currentQuizData.length
        })
    });
}

// 3. Mistake Analyzer
document.getElementById('analyze-mistake-btn').addEventListener('click', async () => {
    const q = document.getElementById('mistake-question').value;
    const a = document.getElementById('mistake-answer').value;
    if (!q || !a) return;
    
    showLoading('mistake-result');
    const res = await fetch('/api/mistake', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({question: q, wrong_answer: a})
    });
    const data = await res.json();
    document.getElementById('mistake-result').innerHTML = marked.parse(data.response);
});

// 4. Notes Generator
document.getElementById('generate-notes-btn').addEventListener('click', async () => {
    const text = document.getElementById('notes-text').value;
    const file = document.getElementById('notes-file').files[0];
    if (!text && !file) return;
    
    showLoading('notes-result');
    const formData = new FormData();
    if (text) formData.append('text', text);
    if (file) formData.append('file', file);
    
    try {
        const res = await fetch('/api/notes', { method: 'POST', body: formData });
        const data = await parseApiResponse(res);
        document.getElementById('notes-result').innerHTML = marked.parse(data.notes);
    } catch (err) {
        document.getElementById('notes-result').textContent = `Upload failed: ${err.message}`;
    }
});

// 5. Progress Tracker
let progressChart = null;

async function loadProgress() {
    const res = await fetch('/api/progress');
    const data = await res.json();
    if(data.status !== 'success') return;
    
    const d = data.data;
    document.getElementById('avg-score').textContent = `${d.average_score_percent}%`;
    
    // Recent Quizzes List
    const recent = document.getElementById('recent-scores-list');
    recent.innerHTML = '';
    
    // Sort scores for the chart
    const chartData = [...d.recent_scores].reverse();
    const labels = chartData.map(s => new Date(s.timestamp).toLocaleDateString());
    const scores = chartData.map(s => (s.score / s.total) * 100);

    d.recent_scores.forEach(s => {
        const dStr = new Date(s.timestamp).toLocaleDateString();
        recent.innerHTML += `<li><span>${s.topic}</span> <span>${s.score}/${s.total} (${dStr})</span></li>`;
    });
    
    // Weak Topics List
    const weak = document.getElementById('weak-topics-list');
    weak.innerHTML = '';
    d.weak_topics.forEach(w => {
        weak.innerHTML += `<li><span>${w.topic}</span> <span>${w.mistake_count} Mistakes</span></li>`;
    });

    // Render Progress History Chart
    const ctx = document.getElementById('progress-history-chart').getContext('2d');
    if (progressChart) progressChart.destroy();

    progressChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Quiz Score (%)',
                data: scores,
                borderColor: '#6366f1',
                backgroundColor: 'rgba(99, 102, 241, 0.1)',
                tension: 0.4,
                fill: true,
                pointBackgroundColor: '#6366f1',
                pointRadius: 5
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: { 
                    beginAtZero: true, 
                    max: 100,
                    ticks: { color: '#94a3b8' },
                    grid: { color: 'rgba(255, 255, 255, 0.05)' }
                },
                x: { 
                    ticks: { color: '#94a3b8' },
                    grid: { display: false }
                }
            }
        }
    });
}

// Voice Assistant (STT & TTS)
let ttsEnabled = true;
const muteTtsBtn = document.getElementById('mute-tts-btn');
const voiceBtn = document.getElementById('voice-btn');

// Toggle Mute
if (muteTtsBtn) {
    muteTtsBtn.addEventListener('click', () => {
        ttsEnabled = !ttsEnabled;
        if (ttsEnabled) {
            muteTtsBtn.innerHTML = '<i class="fa-solid fa-volume-high"></i>';
            muteTtsBtn.style.color = 'var(--text-muted)';
        } else {
            muteTtsBtn.innerHTML = '<i class="fa-solid fa-volume-xmark"></i>';
            muteTtsBtn.style.color = 'var(--danger)';
            window.speechSynthesis.cancel();
        }
    });
}

// Speech to Text
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
if (SpeechRecognition) {
    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.lang = 'en-US';
    
    recognition.onstart = () => {
        if(voiceBtn) voiceBtn.classList.add('recording');
    };
    
    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        if(userInput) userInput.value = transcript;
        if(voiceBtn) voiceBtn.classList.remove('recording');
        // Automatically submit the form
        if(chatForm) chatForm.dispatchEvent(new Event('submit'));
    };
    
    recognition.onerror = () => {
        if(voiceBtn) voiceBtn.classList.remove('recording');
    };
    
    recognition.onend = () => {
        if(voiceBtn) voiceBtn.classList.remove('recording');
    };
    
    if (voiceBtn) {
        voiceBtn.addEventListener('click', () => {
            if (voiceBtn.classList.contains('recording')) {
                recognition.stop();
            } else {
                recognition.start();
            }
        });
    }
} else {
    if (voiceBtn) {
        voiceBtn.style.display = 'none'; // Hide if browser doesn't support
    }
}

// Text to Speech
function speakText(text) {
    if (!ttsEnabled || !window.speechSynthesis) return;
    
    window.speechSynthesis.cancel(); // Stop any ongoing speech
    
    // Strip basic markdown so it doesn't read out "asterisk asterisk"
    let cleanText = text.replace(/[*#_`]/g, '');
    
    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    window.speechSynthesis.speak(utterance);
}

// 6. GeoGraph Search Logic
const mapSearchInput = document.getElementById('map-search-input');
const mapSearchBtn = document.getElementById('map-search-btn');
const mapInsights = document.getElementById('map-insights');

if (mapSearchBtn) {
    mapSearchBtn.addEventListener('click', async () => {
        const query = mapSearchInput.value.trim();
        if (!query) return;

        mapSearchBtn.disabled = true;
        mapSearchBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> searching...';
        mapInsights.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> AI is analyzing the map...';

        try {
            const res = await fetch('/api/maps/search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query })
            });
            const result = await res.json();
            if (result.status !== 'success' || !result.data) {
                mapInsights.innerHTML = result.detail || "Error fetching map data.";
                return;
            }
            const data = result.data;

            // 1. Update Map Markers
            markers.forEach(m => map.removeLayer(m));
            markers = [];
            if (routeLayer) {
                map.removeLayer(routeLayer);
                routeLayer = null;
            }

            if (data && data.route_data && data.route_data.source_coords && data.route_data.destination_coords) {
                const source = data.route_data.source_coords;
                const destination = data.route_data.destination_coords;
                const sourceLatLng = [source.lat, source.lon];
                const destinationLatLng = [destination.lat, destination.lon];

                const sourceMarker = L.marker(sourceLatLng).addTo(map)
                    .bindPopup(`<b>Source</b><br>${data.route_data.source}`);
                const destinationMarker = L.marker(destinationLatLng).addTo(map)
                    .bindPopup(`<b>Destination</b><br>${data.route_data.destination}`);

                markers.push(sourceMarker, destinationMarker);
                const path = Array.isArray(data.route_data.route_path) && data.route_data.route_path.length > 1
                    ? data.route_data.route_path.map(point => [point.lat, point.lon])
                    : [sourceLatLng, destinationLatLng];

                routeLayer = L.polyline(path, {
                    color: '#6366f1',
                    weight: 5,
                    opacity: 0.85,
                }).addTo(map);

                map.fitBounds(routeLayer.getBounds(), { padding: [60, 60] });
            } else if (data && data.places && data.places.length > 0) {
                const latlngs = [];
                data.places.forEach(p => {
                    if (p.lat && p.lon) {
                        const marker = L.marker([p.lat, p.lon]).addTo(map)
                            .bindPopup(`<b>${p.name}</b><br>${p.address}`);
                        markers.push(marker);
                        latlngs.push([p.lat, p.lon]);
                    }
                });

                if (latlngs.length > 0) {
                    const bounds = L.latLngBounds(latlngs);
                    map.fitBounds(bounds, { padding: [50, 50] });
                }
            }

            // 2. Update AI Insights
            mapInsights.innerHTML = marked.parse(data.text);

            // 3. Update Chart
            if (data.graph_data) {
                const ctx = document.getElementById('map-chart').getContext('2d');
                if (mapChart) mapChart.destroy();

                mapChart = new Chart(ctx, {
                    type: 'bar',
                    data: {
                        labels: data.graph_data.labels,
                        datasets: [{
                            label: data.graph_data.title,
                            data: data.graph_data.data,
                            backgroundColor: 'rgba(99, 102, 241, 0.5)',
                            borderColor: 'rgba(99, 102, 241, 1)',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        plugins: {
                            legend: { labels: { color: '#1e293b' } },
                        },
                        scales: {
                            y: { ticks: { color: '#64748b' }, grid: { color: 'rgba(0,0,0,0.05)' } },
                            x: { ticks: { color: '#64748b' }, grid: { color: 'rgba(0,0,0,0.05)' } }
                        }
                    }
                });
            }

        } catch (err) {
            console.error(err);
            mapInsights.innerHTML = "Error fetching map data.";
        } finally {
            mapSearchBtn.disabled = false;
            mapSearchBtn.innerHTML = 'Search';
        }
    });
}
