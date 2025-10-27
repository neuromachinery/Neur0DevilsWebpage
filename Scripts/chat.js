const socket = io("/chat")
const inputCheckbox = window.document.querySelector(".switcher-input");
const documentBody = document.body;


inputCheckbox.addEventListener("change", () => {
  let theme = getTheme();

  if (theme == "dark") {
    setTheme("light");
  } else {
    setTheme("dark");
  }
});

function changeBackground() {
  let theme = getTheme();

  if (theme == "dark") {
    documentBody.classList.add("active");
  } else {
    documentBody.classList.remove("active");
  }
}

function checkTheme() {
  let theme = getTheme();
  if (theme == null || theme == undefined || typeof theme != "string") {
    setTheme("light");
  } else {
    if (theme == "dark") {
      setTheme("dark");
    } else {
      setTheme("light");
    }
  }
}

function setTheme(theme = "dark") {
  window.localStorage.setItem("theme", theme);
  changeBackground();
}

function getTheme() {
  return window.localStorage.getItem("theme");
}
checkTheme();

function handleError(error) {
  const errorMessageDiv = document.getElementById("error-message");
  errorMessageDiv.textContent = error;
  errorMessageDiv.style.display = "block";


  setTimeout(() => {
    errorMessageDiv.style.display = "none";
  }, 3000);
}
let notificationsEnabled = true;
function escapeHtml(text) {
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;'
  };
  return text.replace(/[&<>"']/g, function (m) { return map[m]; });
}
document.addEventListener("DOMContentLoaded", loadChatHistory);
function showOverlay(objectUrl, filename) {
  const overlay = document.getElementById('media-overlay');
  const content = document.getElementById('media-content');
  content.innerHTML = '';

  let element;
  if (filename.match(/\.(jpg|jpeg|png|gif)$/i)) {
    element = document.createElement('img');
    element.src = objectUrl;
    element.style.maxWidth = '90vw';
    element.style.maxHeight = '90vh';
  } else if (filename.match(/\.(mp4|webm|ogg)$/i)) {
    element = document.createElement('video');
    element.src = objectUrl;
    element.controls = true;
    element.autoplay = true;
    element.style.maxWidth = '90vw';
    element.style.maxHeight = '90vh';
  } else {

    const a = document.createElement('a');
    a.href = objectUrl;
    a.download = filename;
    a.click();
  }
  content.appendChild(element);

  overlay.style.display = 'flex';


  overlay.onclick = function (e) {
    if (e.target === overlay) {
      overlay.style.display = 'none';
      content.innerHTML = '';
      URL.revokeObjectURL(objectUrl);
    }
  }
}
function handleFileClick(url, filename, progressId) {
  const xhr = new XMLHttpRequest();
  xhr.open('GET', url, true);
  xhr.responseType = 'blob';

  xhr.onprogress = function (event) {
    if (event.lengthComputable) {
      const percent = Math.floor((event.loaded / event.total) * 100);
      document.getElementById(progressId).textContent = percent + '%';
    }
  };

  xhr.onload = function () {
    if (xhr.status === 200) {
      document.getElementById(progressId).textContent = '';
      const blob = xhr.response;
      const objectUrl = URL.createObjectURL(blob);


      if (filename.match(/\.(jpg|jpeg|png|gif)$/i)) {
        showOverlay(objectUrl, filename);
      } else if (filename.match(/\.(mp4|webm|ogg)$/i)) {
        showOverlay(objectUrl, filename);
      } else {

        const a = document.createElement('a');
        a.href = objectUrl;
        a.download = filename;
        a.style.display = 'none';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(objectUrl);
      }
    } else {
      document.getElementById(progressId).textContent = 'Error';
      alert('Download failed');
    }
  };

  xhr.onerror = function () {
    document.getElementById(progressId).textContent = 'Error';
    alert('Download failed');
  };

  xhr.send();
}
function renderMessage(data) {
  const messagesDiv = document.getElementById("messages");
  const messageElement = document.createElement("div");

  const nameColor = stringToColor(data.name + data.ip);
  const nameSpan = `<span style="color: ${nameColor}; font-weight: bold;">${data.name}</span>`;

  if (data.unique_id) {
    const originalFilename = data.message;
    const progressId = `progress-${data.unique_id}`;
    const fileLink = `<a href="#" 
              onclick="handleFileClick('/download/${data.unique_id}', '${originalFilename}', '${progressId}')">
              ${originalFilename}
            </a>`;

    messageElement.innerHTML = `${nameSpan}: ${fileLink} <span id="${progressId}" style="margin-left:8px;"></span>`;
  } else {
    messageElement.innerHTML = `${nameSpan}: ${data.message}`;
  }

  messagesDiv.appendChild(messageElement);
}


function loadChatHistory() {
  fetch("/chat_history")
    .then((response) => response.json())
    .then((data) => {
      const messagesDiv = document.getElementById("messages");
      messagesDiv.innerHTML = "";

      data.messages.forEach((msg) => {
        renderMessage({
          name: msg.name,
          message: msg.message,
          unique_id: msg.unique_id,
          ip: msg.ip,
          time: msg.time,
        });
      });
      messagesDiv.scrollTop = messagesDiv.scrollHeight;
    })
    .catch((error) =>
      console.error("Error loading chat history:", error)
    );
}

socket.on("receive_message", function (data) {
  renderMessage(data);
  messagesDiv = document.getElementById("messages");
  messagesDiv.scrollTop = messagesDiv.scrollHeight;

  if (notificationsEnabled && data.name !== userName) {
    showNotification(data.name, data.message);
    playNotificationSound();
  }
});
function playNotificationSound() {
  const notificationSound = document.getElementById("notificationSound");
  notificationSound.currentTime = 0;
  notificationSound.play();
}
function showNotification(name, message) {
  if (Notification.permission === "granted") {
    new Notification(`${name} написал:`, { body: message });
  } else if (Notification.permission !== "denied") {
    Notification.requestPermission().then((permission) => {
      if (permission === "granted") {
        new Notification(`${name} написал:`, { body: message });
      }
    });
  }
}

function sendMessage(event) {
  event.preventDefault();
  userName = document.getElementById("name").value;
  message = document.getElementById("message").value;

  socket.emit("send_message", {
    name: userName,
    message: message,
    channel: -1,
    external: false,
  });

  document.getElementById("message").value = "";
  messagesDiv = document.getElementById("messages");
  messagesDiv.scrollTop = messagesDiv.scrollHeight;
}
document.getElementById("notificationToggle").addEventListener("click", function () {
  notificationsEnabled = !notificationsEnabled;
  updateNotificationText(this, notificationsEnabled);
});

function updateNotificationText(button, isEnabled) {
  const locale = document.getElementById('localisation').textContent.toLowerCase();

  if (locale === 'ru') {
    button.textContent = isEnabled ? "Отключить уведомления" : "Включить уведомления";
  } else {
    button.textContent = isEnabled ? "Disable notifications" : "Enable notifications";
  }
}
const dropZone = document.getElementById("drop_zone");

dropZone.addEventListener("dragover", (event) => {
  event.preventDefault();
  dropZone.style.borderColor = "#00a500";
});

dropZone.addEventListener("dragleave", () => {
  dropZone.style.borderColor = "#ccc";
});

dropZone.addEventListener("drop", (event) => {
  event.preventDefault();
  name = document.getElementById("name").value;
  dropZone.style.borderColor = "#ccc";
  const files = event.dataTransfer.files;
  uploadFiles(files, name);
});
function stringToColor(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
    hash = hash & hash;
  }
  let color = '#';
  for (let i = 0; i < 3; i++) {

    const value = (hash >> (i * 8)) & 0xFF;
    color += ('00' + value.toString(16)).slice(-2);
  }
  return color;
}
function lerpColor(a, b, t) {

  const ah = parseInt(a.replace('#', ''), 16),
    bh = parseInt(b.replace('#', ''), 16),
    ar = (ah >> 16) & 0xff, ag = (ah >> 8) & 0xff, ab = ah & 0xff,
    br = (bh >> 16) & 0xff, bg = (bh >> 8) & 0xff, bb = bh & 0xff,
    rr = ar + t * (br - ar),
    rg = ag + t * (bg - ag),
    rb = ab + t * (bb - ab);
  return '#' + (((1 << 24) + (rr << 16) + (rg << 8) + (rb | 0)).toString(16).slice(1));
}
function updateDropZoneProgress(percent) {

  const dropZone = document.getElementById('drop_zone');
  const isDark = document.body.classList.contains('active');

  const startBg = isDark ? '#393c46' : '#cecece';
  const endBg = isDark ? '#cecece' : '#393c46';
  const startBorder = isDark ? '#292c35' : '#f1f1f1';
  const endBorder = isDark ? '#f1f1f1' : '#292c35';
  dropZone.style.backgroundColor = lerpColor(startBg, endBg, percent);
  dropZone.style.borderColor = lerpColor(startBorder, endBorder, percent);
}
function uploadFiles(files, name) {
  const formData = new FormData();
  for (let i = 0; i < files.length; i++) {
    formData.append("file", files[i]);
  }

  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/upload", true);

  xhr.upload.onprogress = function (event) {
    if (event.lengthComputable) {
      const percent = event.loaded / event.total;
      updateDropZoneProgress(percent);
    }
  };

  xhr.onload = function () {
    updateDropZoneProgress(0);
    if (xhr.status === 200) {
      const data = JSON.parse(xhr.responseText);
      if (data.success) {
        socket.emit("send_message", {
          name: name,
          message: data.original_filename,
          unique_id: data.unique_id,
          channel: -1,
          external: false,
        });
      }
    } else {
      const data = JSON.parse(xhr.responseText);
      handleError(data.error);
    }
    setTimeout(() => updateDropZoneProgress(0), 500);
  };

  xhr.onerror = function () {
    handleError("Upload failed");
    updateDropZoneProgress(0);
  };

  xhr.send(formData);
}

function toggleBottomMenu() {
  const menu = document.getElementById('bottomMenu');
  const overlay = document.querySelector('.overlay');

  menu.classList.toggle('active');
  overlay.classList.toggle('active');

  // Блокировка скролла
  document.body.style.overflow = menu.classList.contains('active') ? 'hidden' : '';
}

// Закрытие меню при нажатии Escape
document.addEventListener('keydown', function (event) {
  if (event.key === 'Escape') {
    const menu = document.getElementById('bottomMenu');
    if (menu.classList.contains('active')) {
      toggleBottomMenu();
    }
  }
});

function updateTime() {
  const timeDisplay = document.getElementById('Clock');
  const now = new Date(); // Убрали 24 - это неправильный параметр

  // 24-часовой формат с опциями
  const options = {
    hour12: false, // 24-часовой формат
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  };

  timeDisplay.textContent = now.toLocaleTimeString('ru-RU', options);
}

updateTime();
setInterval(updateTime, 1000);

function ChangeTheme(themeName) {
  const themeLink = document.getElementById('theme');
  themeLink.href = `/CSS/chat_themes/${themeName}.css`;
  currentTheme = themeName;

  // Сохраняем в localStorage
  localStorage.setItem('selectedTheme', themeName);


  console.log(`Тема установлена: ${themeName}`);
}


// Загрузка сохраненной темы
function loadTheme() {
  const savedTheme = localStorage.getItem('selectedTheme');
  if (savedTheme) {
    ChangeTheme(savedTheme);
  }
}

// Загружаем тему при старте
document.addEventListener('DOMContentLoaded', loadTheme);

function ChangeLocale() {
  var locale = document.getElementById("localisation").textContent;
  if (locale === "ru") {
    locale = "en";
    document.getElementById("localisation").textContent = "en";
    document.getElementById('CH').textContent = "Chat";
    document.getElementById('name').placeholder = "Name";
    document.getElementById('message').placeholder = "Message";
    document.getElementById('SendButton').textContent = "Send";
    document.getElementById('drop_zone').textContent = "Drop files here";
    document.getElementById('returnButton').textContent = "Return to main page";
    document.getElementById('ThemeButton').textContent = "Theme";
    document.getElementById('menu-header').textContent = "Navigation";
    document.getElementById('menu-button-main').textContent = "🏠 Main";
    document.getElementById('menu-button-about').textContent = "❔ About";
    document.getElementById('menu-button-drop').textContent = "📥 Get drop";
    document.getElementById('menu-button-make_drop').textContent = "📤 Make drop";
    document.getElementById('menu-button-direct').textContent = "📨 Direct";
    document.getElementById('menu-button-ctrl').textContent = "❔ ctrl";
    if (document.getElementById('notificationToggle').textContent === "Отключить уведомления") {
      document.getElementById('notificationToggle').textContent = "Disable notifications";
    } else { document.getElementById('notificationToggle').textContent = "Enable notifications"; }

  } else {
    locale = "ru";
    document.getElementById("localisation").textContent = "ru";
    document.getElementById('CH').textContent = "Чат";
    document.getElementById('name').placeholder = "Ваше имя";
    document.getElementById('message').placeholder = "Ваше сообщение";
    document.getElementById('SendButton').textContent = "Отправить";
    document.getElementById('drop_zone').textContent = "Отправить файл";
    document.getElementById('returnButton').textContent = "Вернуться на главную страницу";
    document.getElementById('ThemeButton').textContent = "Тема";
    document.getElementById('menu-header').textContent = "Навигация";
    document.getElementById('menu-button-main').textContent = "🏠 Главная";
    document.getElementById('menu-button-about').textContent = "❔ Обо мне";
    document.getElementById('menu-button-drop').textContent = "📥 Получить дроп";
    document.getElementById('menu-button-make_drop').textContent = "📤 Создать дроп";
    document.getElementById('menu-button-direct').textContent = "📨 Личка";
    document.getElementById('menu-button-ctrl').textContent = "❔ ctrl";
    if (document.getElementById('notificationToggle').textContent === "Disable notifications") {
      document.getElementById('notificationToggle').textContent = "Отключить уведомления";
    } else { document.getElementById('notificationToggle').textContent = "Включить уведомления"; }
  }

}
document.addEventListener('DOMContentLoaded', function() {
    ChangeLocale(); // Запускается после загрузки DOM
});
// Применить локаль к странице
function applyLocale(locale) {
  document.getElementById('localisation').textContent = locale;
  console.log('Локаль применена:', locale);
}

// Установить и сохранить локаль
function setLocale(locale) {
  localStorage.setItem('localisation', locale);
  applyLocale(locale);
}

// Загрузить сохраненную локаль при загрузке страницы
document.addEventListener('DOMContentLoaded', function () {
  const savedLocale = localStorage.getItem('localisation') || 'Ru';
  applyLocale(savedLocale);
});