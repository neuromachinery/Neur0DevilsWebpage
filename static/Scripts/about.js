function launchTeamSpeak() {
    // Создаем невидимую ссылку
    const link = document.createElement('a');
    link.href = 'ts3server://195.122.224.152';
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}