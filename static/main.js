const firebaseConfig = {
  apiKey: "AIzaSyAdZzm_m9rSB0sNOHAhe-Z57zKLSkvmDwY",
  authDomain: "mindmate-d294b.firebaseapp.com",
  projectId: "mindmate-d294b",
  storageBucket: "mindmate-d294b.appspot.com",
  messagingSenderId: "79383956961",
  appId: "1:79383956961:web:da7dd36151520454ab96a0",
  measurementId: "G-MSSJ3LWR5N"
};
firebase.initializeApp(firebaseConfig);

// Add theme toggle functionality
let currentTheme = localStorage.getItem('theme') || 'light';
document.body.setAttribute('data-theme', currentTheme);

function toggleTheme() {
  currentTheme = currentTheme === 'light' ? 'dark' : 'light';
  document.body.setAttribute('data-theme', currentTheme);
  localStorage.setItem('theme', currentTheme);
}

// --- Auth UI Elements ---
const authContainer = document.getElementById('auth-container');
const appRoot = document.getElementById('app-root');
const loginTab = document.getElementById('login-tab');
const registerTab = document.getElementById('register-tab');
const loginForm = document.getElementById('login-form');
const registerForm = document.getElementById('register-form');
const authError = document.getElementById('auth-error');

// --- Auth tab switching with animation ---
loginTab.onclick = () => {
  loginTab.classList.add('active');
  registerTab.classList.remove('active');
  document.getElementById('auth-tabs').classList.remove('register-active');
  loginForm.style.display = '';
  registerForm.style.display = 'none';
  loginForm.classList.remove('fadeIn');
  void loginForm.offsetWidth; // trigger reflow
  loginForm.classList.add('fadeIn');
  authError.textContent = '';
};
registerTab.onclick = () => {
  registerTab.classList.add('active');
  loginTab.classList.remove('active');
  document.getElementById('auth-tabs').classList.add('register-active');
  loginForm.style.display = 'none';
  registerForm.style.display = '';
  registerForm.classList.remove('fadeIn');
  void registerForm.offsetWidth;
  registerForm.classList.add('fadeIn');
  authError.textContent = '';
};

// --- Auth form submission ---
loginForm.onsubmit = async (e) => {
  e.preventDefault();
  const email = document.getElementById('login-email').value.trim();
  const password = document.getElementById('login-password').value;
  try {
    await firebase.auth().signInWithEmailAndPassword(email, password);
  } catch (err) {
    authError.textContent = err.message;
    authError.style.opacity = 1;
  }
};

registerForm.onsubmit = async (e) => {
  e.preventDefault();
  const email = document.getElementById('register-email').value.trim();
  const password = document.getElementById('register-password').value;
  try {
    await firebase.auth().createUserWithEmailAndPassword(email, password);
  } catch (err) {
    authError.textContent = err.message;
    authError.style.opacity = 1;
  }
};

// --- Google sign-in ---
document.getElementById('google-login').onclick =
document.getElementById('google-register').onclick = async () => {
  const provider = new firebase.auth.GoogleAuthProvider();
  try {
    await firebase.auth().signInWithPopup(provider);
  } catch (err) {
    authError.textContent = err.message;
    authError.style.opacity = 1;
  }
};

// --- API Helpers ---
async function fetchAPI(endpoint, method = 'GET', data = null) {
  const options = {
    method,
    headers: {
      'Content-Type': 'application/json',
    }
  };

  if (data) {
    options.body = JSON.stringify(data);
  }

  // Add Firebase auth token if user is logged in
  const user = firebase.auth().currentUser;
  if (user) {
    const token = await user.getIdToken();
    options.headers['Authorization'] = `Bearer ${token}`;
  }

  try {
    const response = await fetch(endpoint, options);
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.error('API request failed:', error);
    throw error;
  }
}

// --- Main App UI Pages ---
const pages = {
  chat: {
    icon: "💬",
    label: "Chat",
    render: () => `
      <div class="page-header">
        <h2>Chat with MindMate</h2>
      </div>
      <div class="page-desc">Talk to MindMate and get support instantly. I'm here to listen and help.</div>
      
      <div class="chat-container">
        <div class="chat-messages" id="chat-messages">
          <div class="message bot">
            <div class="message-content">
              Hello! I'm MindMate, your personal wellness assistant. How are you feeling today?
              <div class="message-time">${new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</div>
            </div>
          </div>
        </div>
        <div class="chat-input-container">
          <button class="voice-btn" id="voice-btn" title="Voice input">🎤</button>
          <input type="text" class="chat-input" id="chat-input" placeholder="Type a message...">
          <button class="send-btn" id="send-btn" title="Send message">➤</button>
        </div>
      </div>
    `
  },
  journal: {
    icon: "📔",
    label: "Journal",
    render: () => `
      <div class="page-header">
        <h2>Your Journal</h2>
      </div>
      <div class="page-desc">Write and reflect on your thoughts. Track your mood over time.</div>
      
      <div class="journal-container">
        <div class="journal-form">
          <h3>New Entry</h3>
          <div class="mood-selector">
            <button class="mood-btn" data-mood="happy">😊 Happy</button>
            <button class="mood-btn" data-mood="sad">😔 Sad</button>
            <button class="mood-btn" data-mood="anxious">😰 Anxious</button>
            <button class="mood-btn" data-mood="angry">😠 Angry</button>
            <button class="mood-btn" data-mood="neutral">😐 Neutral</button>
          </div>
          <textarea id="journal-text" placeholder="How are you feeling today? What's on your mind?"></textarea>
          <button class="btn primary" id="save-journal-btn">Save Entry</button>
        </div>
        
        <div class="journal-list">
          <h3>Recent Entries</h3>
          <div id="journal-entries-container">
            <div class="loading-indicator">Loading your journal entries...</div>
          </div>
        </div>
      </div>
    `
  },
  suggestions: {
    icon: "✨",
    label: "Suggestions",
    render: () => `
      <div class="page-header">
        <h2>Personalized Suggestions</h2>
      </div>
      <div class="page-desc">Based on your mood patterns and journal entries, here are some personalized recommendations.</div>
      
      <div class="mood-analysis">
        <h3>Your Mood Insights</h3>
        <div id="mood-quote" class="mood-quote">
          <div class="loading-indicator">Analyzing your mood patterns...</div>
        </div>
      </div>
      
      <div class="suggestions-container" id="suggestions-container">
        <div class="loading-indicator">Loading your personalized suggestions...</div>
      </div>
    `
  },
  profile: {
    icon: "👤",
    label: "Profile",
    render: () => `
      <div class="page-header">
        <h2>Your Profile</h2>
      </div>
      <div class="page-desc">Manage your account settings and preferences.</div>
      
      <div class="profile-container">
        <div class="profile-card">
          <div class="profile-info">
            <div class="profile-avatar">
              ${firebase.auth().currentUser?.email?.charAt(0).toUpperCase() || 'U'}
            </div>
            <div class="profile-details">
              <h3>${firebase.auth().currentUser?.displayName || 'User'}</h3>
              <p>${firebase.auth().currentUser?.email || ''}</p>
            </div>
          </div>
          <button class="btn primary" onclick="signOut()">Sign Out</button>
        </div>
      </div>
    `
  }
};

// --- Enhanced Sidebar & Content Rendering ---
function renderSidebar(activePage, user) {
  const firstLetter = user?.email?.charAt(0).toUpperCase() || 'U';
  
  return `
    <div class="logo-container">
      <div class="logo">
        <span class="logo-icon">🧠</span>
        <span class="logo-text">MindMate</span>
      </div>
      <button class="sidebar-toggle" id="sidebar-toggle" title="Toggle sidebar">≡</button>
    </div>
    <nav class="sidebar-nav">
      ${Object.entries(pages).map(([key, page]) => `
        <button class="${activePage === key ? "active" : ""}" data-page="${key}" title="${page.label}">
          <span class="icon">${page.icon}</span>
          <span class="label">${page.label}</span>
        </button>
      `).join('')}
    </nav>
    <div class="user-section">
      <div class="user-avatar" title="${user?.displayName || 'User'}">${firstLetter}</div>
      <div class="user-info">
        <div class="user-name">${user?.displayName || 'User'}</div>
        <div class="user-email">${user?.email || ''}</div>
      </div>
      <button class="signout-btn" onclick="signOut()" title="Sign out">⎋</button>
    </div>
  `;
}

function renderMainContent(pageKey) {
  return pages[pageKey].render();
}

function mountApp(pageKey = "chat") {
  const user = firebase.auth().currentUser;
  
  appRoot.innerHTML = `
    <aside class="sidebar" id="sidebar">
      ${renderSidebar(pageKey, user)}
    </aside>
    <main class="main-content">
      ${renderMainContent(pageKey)}
    </main>
    <button class="theme-toggle" onclick="toggleTheme()" title="Toggle dark/light mode">
      <span class="theme-toggle-light">☀️</span>
      <span class="theme-toggle-dark">🌙</span>
    </button>
  `;

  // Sidebar navigation event listeners
  appRoot.querySelectorAll('.sidebar-nav button').forEach(btn => {
    btn.onclick = () => mountApp(btn.dataset.page);
  });
  
  // Sidebar toggle
  const sidebarToggle = document.getElementById('sidebar-toggle');
  const sidebar = document.getElementById('sidebar');
  if (sidebarToggle && sidebar) {
    sidebarToggle.onclick = () => {
      sidebar.classList.toggle('collapsed');
    }
  }
  
  // Page-specific event listeners
  if (pageKey === 'chat') {
    setupChatEventListeners();
  }
  
  if (pageKey === 'journal') {
    setupJournalEventListeners();
    loadJournalEntries();
  }
  
  if (pageKey === 'suggestions') {
    loadSuggestions();
  }
  
  // Make theme toggle function available globally
  window.toggleTheme = toggleTheme;
}

// --- Page-specific event listeners ---
function setupChatEventListeners() {
  const chatInput = document.getElementById('chat-input');
  const sendBtn = document.getElementById('send-btn');
  const voiceBtn = document.getElementById('voice-btn');
  const chatMessages = document.getElementById('chat-messages');
  
  if (!chatInput || !sendBtn || !voiceBtn || !chatMessages) return;
  
  const sendMessage = async () => {
    const message = chatInput.value.trim();
    if (!message) return;
    
    // Add user message to chat
    const now = new Date();
    const time = now.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
    
    chatMessages.innerHTML += `
      <div class="message user">
        <div class="message-content">
          ${message}
          <div class="message-time">${time}</div>
        </div>
      </div>
    `;
    
    chatInput.value = '';
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    // Add loading indicator
    const loadingId = 'loading-' + Date.now();
    chatMessages.innerHTML += `
      <div class="message bot" id="${loadingId}">
        <div class="message-content">
          <div class="typing-indicator">
            <span></span><span></span><span></span>
          </div>
        </div>
      </div>
    `;
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    try {
      // Call the backend API
      const user = firebase.auth().currentUser;
      const response = await fetchAPI('/chat', 'POST', {
        message: message,
        user_id: user.uid
      });
      
      // Remove loading indicator
      document.getElementById(loadingId)?.remove();
      
      // Add bot response
      chatMessages.innerHTML += `
        <div class="message bot">
          <div class="message-content">
            ${response.reply}
            <div class="message-time">${now.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</div>
          </div>
        </div>
      `;
      chatMessages.scrollTop = chatMessages.scrollHeight;
    } catch (error) {
      // Remove loading indicator
      document.getElementById(loadingId)?.remove();
      
      // Add error message
      chatMessages.innerHTML += `
        <div class="message bot">
          <div class="message-content">
            Sorry, I couldn't process your message. Please try again.
            <div class="message-time">${now.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</div>
          </div>
        </div>
      `;
      chatMessages.scrollTop = chatMessages.scrollHeight;
    }
  };
  
  sendBtn.onclick = sendMessage;
  chatInput.onkeypress = (e) => {
    if (e.key === 'Enter') {
      sendMessage();
      e.preventDefault();
    }
  };
  
  let isRecording = false;
  let mediaRecorder = null;
  let audioChunks = [];
  
  voiceBtn.onclick = async () => {
    if (isRecording) {
      // Stop recording
      mediaRecorder.stop();
      voiceBtn.classList.remove('recording');
      isRecording = false;
    } else {
      try {
        // Start recording
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];
        
        mediaRecorder.addEventListener("dataavailable", event => {
          audioChunks.push(event.data);
        });
        
        mediaRecorder.addEventListener("stop", async () => {
          // Create audio blob and send to server
          const audioBlob = new Blob(audioChunks, { type: 'audio/mpeg' });
          const formData = new FormData();
          formData.append('audio', audioBlob, 'recording.mp3');
          formData.append('user_id', firebase.auth().currentUser.uid);
          
          // Add loading indicator
          const loadingId = 'loading-' + Date.now();
          chatMessages.innerHTML += `
            <div class="message bot" id="${loadingId}">
              <div class="message-content">
                <div class="typing-indicator">
                  <span></span><span></span><span></span>
                </div>
              </div>
            </div>
          `;
          chatMessages.scrollTop = chatMessages.scrollHeight;
          
          try {
            const response = await fetch('/voice', {
              method: 'POST',
              body: formData
            });
            
            const data = await response.json();
            
            // Remove loading indicator
            document.getElementById(loadingId)?.remove();
            
            // Add bot response
            const now = new Date();
            chatMessages.innerHTML += `
              <div class="message bot">
                <div class="message-content">
                  ${data.reply}
                  <div class="message-time">${now.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</div>
                </div>
              </div>
            `;
            chatMessages.scrollTop = chatMessages.scrollHeight;
          } catch (error) {
            // Remove loading indicator
            document.getElementById(loadingId)?.remove();
            
            // Add error message
            const now = new Date();
            chatMessages.innerHTML += `
              <div class="message bot">
                <div class="message-content">
                  Sorry, I couldn't process your voice message. Please try again or type your message.
                  <div class="message-time">${now.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</div>
                </div>
              </div>
            `;
            chatMessages.scrollTop = chatMessages.scrollHeight;
          }
          
          // Stop all tracks
          stream.getTracks().forEach(track => track.stop());
        });
        
        mediaRecorder.start();
        voiceBtn.classList.add('recording');
        isRecording = true;
      } catch (error) {
        console.error('Error accessing microphone:', error);
        alert('Could not access your microphone. Please check your browser permissions.');
      }
    }
  };
}

async function loadJournalEntries() {
  const entriesContainer = document.getElementById('journal-entries-container');
  if (!entriesContainer) return;
  
  try {
    const user = firebase.auth().currentUser;
    const response = await fetchAPI(`/get_journal?user_id=${user.uid}`);
    
    if (response.journals && response.journals.length > 0) {
      // Display journal entries
      entriesContainer.innerHTML = '';
      
      response.journals.forEach(entry => {
        const date = new Date(entry.timestamp);
        const formattedDate = date.toLocaleDateString('en-US', { 
          year: 'numeric', 
          month: 'short', 
          day: 'numeric' 
        });
        
        // Analyze the sentiment of the entry to determine the mood class
        let moodClass = 'neutral';
        let moodEmoji = '😐';
        
        // Simplified sentiment analysis (in production, this would be done server-side)
        const text = entry.journal.toLowerCase();
        if (text.includes('happy') || text.includes('joy') || text.includes('excited')) {
          moodClass = 'happy';
          moodEmoji = '😊';
        } else if (text.includes('sad') || text.includes('unhappy') || text.includes('depressed')) {
          moodClass = 'sad';
          moodEmoji = '😔';
        } else if (text.includes('angry') || text.includes('frustrat') || text.includes('annoyed')) {
          moodClass = 'angry';
          moodEmoji = '😠';
        } else if (text.includes('anxious') || text.includes('worry') || text.includes('nervous')) {
          moodClass = 'anxious';
          moodEmoji = '😰';
        }
        
        entriesContainer.innerHTML += `
          <div class="journal-entry ${moodClass}">
            <div class="journal-entry-header">
              <span class="journal-date">${formattedDate}</span>
              <span class="journal-mood">${moodEmoji} ${moodClass.charAt(0).toUpperCase() + moodClass.slice(1)}</span>
            </div>
            <div class="journal-content">
              ${entry.journal}
            </div>
          </div>
        `;
      });
    } else {
      entriesContainer.innerHTML = `<div class="empty-state">No journal entries yet. Start by creating a new entry!</div>`;
    }
  } catch (error) {
    console.error('Error loading journal entries:', error);
    entriesContainer.innerHTML = `<div class="error-state">Failed to load journal entries. Please try again later.</div>`;
  }
}

function setupJournalEventListeners() {
  const moodButtons = document.querySelectorAll('.mood-btn');
  const saveButton = document.getElementById('save-journal-btn');
  const journalText = document.getElementById('journal-text');
  
  let selectedMood = null;
  
  moodButtons.forEach(btn => {
    btn.onclick = () => {
      moodButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      selectedMood = btn.dataset.mood;
    };
  });
  
  if (saveButton && journalText) {
    saveButton.onclick = async () => {
      const text = journalText.value.trim();
      if (!text) {
        alert('Please write something in your journal before saving.');
        return;
      }
      
      try {
        const user = firebase.auth().currentUser;
        await fetchAPI('/add_journal', 'POST', {
          user_id: user.uid,
          journal: text
        });
        
        // Clear form and update journal list
        journalText.value = '';
        moodButtons.forEach(b => b.classList.remove('active'));
        selectedMood = null;
        
        // Show success message
        alert('Journal entry saved successfully!');
        
        // Reload journal entries
        loadJournalEntries();
      } catch (error) {
        console.error('Error saving journal entry:', error);
        alert('Failed to save journal entry. Please try again.');
      }
    };
  }
}

async function loadSuggestions() {
  const suggestionsContainer = document.getElementById('suggestions-container');
  const moodQuote = document.getElementById('mood-quote');
  
  if (!suggestionsContainer || !moodQuote) return;
  
  try {
    const user = firebase.auth().currentUser;
    const response = await fetchAPI('/recommend', 'POST', {
      user_id: user.uid
    });
    
    // Display quote
    moodQuote.innerHTML = `
      <div class="quote">
        <span class="quote-mark">"</span>
        ${response.quote}
        <span class="quote-mark">"</span>
      </div>
      <div class="mood-indicator">
        Your current mood: <span class="mood-value ${response.mood}">${response.mood.charAt(0).toUpperCase() + response.mood.slice(1)}</span>
      </div>
    `;
    
    // Display suggestions
    suggestionsContainer.innerHTML = '';
    
    // Helper function to get appropriate icon for suggestion
    function getSuggestionIcon(suggestion) {
      const lowercased = suggestion.toLowerCase();
      if (lowercased.includes('meditat') || lowercased.includes('breath')) return '🧘';
      if (lowercased.includes('walk') || lowercased.includes('run') || lowercased.includes('exercise')) return '🏃';
      if (lowercased.includes('gratitude') || lowercased.includes('journal')) return '📝';
      if (lowercased.includes('music') || lowercased.includes('listen')) return '🎵';
      if (lowercased.includes('friend') || lowercased.includes('talk') || lowercased.includes('call')) return '👥';
      if (lowercased.includes('book') || lowercased.includes('read')) return '📚';
      if (lowercased.includes('water') || lowercased.includes('drink')) return '💧';
      if (lowercased.includes('sleep') || lowercased.includes('rest')) return '😴';
      return '✨'; // Default icon
    }
    
    // Helper function to get category for suggestion
    function getSuggestionCategory(suggestion) {
      const lowercased = suggestion.toLowerCase();
      if (lowercased.includes('meditat') || lowercased.includes('breath')) return 'Mindfulness';
      if (lowercased.includes('walk') || lowercased.includes('run') || lowercased.includes('exercise')) return 'Exercise';
      if (lowercased.includes('gratitude') || lowercased.includes('journal')) return 'Positivity';
      if (lowercased.includes('music') || lowercased.includes('listen')) return 'Relaxation';
      if (lowercased.includes('friend') || lowercased.includes('talk') || lowercased.includes('call')) return 'Social';
      if (lowercased.includes('book') || lowercased.includes('read')) return 'Learning';
      if (lowercased.includes('water') || lowercased.includes('drink')) return 'Health';
      if (lowercased.includes('sleep') || lowercased.includes('rest')) return 'Rest';
      return 'Wellness'; // Default category
    }
    
    // Generate suggestion cards
    response.suggestions.slice(0, 4).forEach(suggestion => {
      const icon = getSuggestionIcon(suggestion);
      const category = getSuggestionCategory(suggestion);
      
      suggestionsContainer.innerHTML += `
        <div class="suggestion-card">
          <div class="suggestion-icon">${icon}</div>
          <div class="suggestion-title">${suggestion.split(' ').slice(0, 3).join(' ')}</div>
          <div class="suggestion-text">
            ${suggestion}
          </div>
          <div class="suggestion-footer">
            <div class="suggestion-category">${category}</div>
            <div class="suggestion-action">Try now</div>
          </div>
        </div>
      `;
    });
    
    // Add book and movie suggestions if available
    if (response.details && response.details.books && response.details.books.length > 0) {
      suggestionsContainer.innerHTML += `
        <div class="suggestion-card">
          <div class="suggestion-icon">📚</div>
          <div class="suggestion-title">Book Recommendations</div>
          <div class="suggestion-text">
            <ul class="suggestion-list">
              ${response.details.books.slice(0, 3).map(book => `<li>${book}</li>`).join('')}
            </ul>
          </div>
          <div class="suggestion-footer">
            <div class="suggestion-category">Reading</div>
            <div class="suggestion-action">Explore</div>
          </div>
        </div>
      `;
    }
    
    if (response.details && response.details.movies && response.details.movies.length > 0) {
      suggestionsContainer.innerHTML += `
        <div class="suggestion-card">
          <div class="suggestion-icon">🎬</div>
          <div class="suggestion-title">Movie Recommendations</div>
          <div class="suggestion-text">
            <ul class="suggestion-list">
              ${response.details.movies.slice(0, 3).map(movie => `<li>${movie}</li>`).join('')}
            </ul>
          </div>
          <div class="suggestion-footer">
            <div class="suggestion-category">Entertainment</div>
            <div class="suggestion-action">Watch</div>
          </div>
        </div>
      `;
    }
  } catch (error) {
    console.error('Error loading suggestions:', error);
    suggestionsContainer.innerHTML = `<div class="error-state">Failed to load suggestions. Please try again later.</div>`;
    moodQuote.innerHTML = `<div class="error-state">Could not analyze your mood at this time.</div>`;
  }
}

// --- Auth state handling ---
firebase.auth().onAuthStateChanged(user => {
  if (user) {
    // User is signed in
    authContainer.style.display = 'none';
    appRoot.style.display = '';
    mountApp("chat");
  } else {
    // User is signed out
    authContainer.style.display = '';
    appRoot.style.display = 'none';
  }
});

// --- Sign out function ---
window.signOut = () => firebase.auth().signOut();