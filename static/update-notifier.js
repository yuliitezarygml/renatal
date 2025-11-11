/**
 * Система обновлений приложения
 * Проверяет наличие обновлений и отображает уведомления пользователю
 */

class UpdateNotificationSystem {
    constructor() {
        this.checkInterval = 5 * 60 * 1000; // Проверка каждые 5 минут
        this.dismissedUpdates = this._loadDismissedUpdates();
        this.currentUpdateVersion = null;
        this.init();
    }

    /**
     * Инициализация системы
     */
    init() {
        // Проверяем обновления при загрузке страницы
        this.checkForUpdates();

        // Установляем периодическую проверку
        setInterval(() => {
            this.checkForUpdates();
        }, this.checkInterval);

        // Слушаем событие фокуса (когда пользователь вернулся на вкладку)
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                this.checkForUpdates();
            }
        });
    }

    /**
     * Проверяет наличие обновлений
     */
    async checkForUpdates() {
        try {
            const response = await fetch('/api/check-update');
            const data = await response.json();

            if (data.success && data.update_available) {
                // Проверяем, не было ли это обновление отклонено
                if (this._isUpdateDismissed(data.github_version)) {
                    console.log('Обновление было отклонено пользователем');
                    return;
                }

                this.currentUpdateVersion = data.github_version;
                this.showUpdateNotification(data);
            }
        } catch (error) {
            console.error('Ошибка при проверке обновлений:', error);
        }
    }

    /**
     * Отображает уведомление об обновлении
     */
    showUpdateNotification(updateData) {
        // Удаляем старое уведомление, если оно есть
        const existingNotification = document.getElementById('update-notification-container');
        if (existingNotification) {
            existingNotification.remove();
        }

        // Форматируем changelog
        const changelogHtml = this._formatChangelog(updateData.changelog);

        const notificationHtml = `
            <div id="update-notification-container" class="update-notification-top">
                <div class="update-notification-content">
                    <div class="update-notification-header">
                        <div class="update-notification-title">
                            <i class="fas fa-cloud-download-alt"></i>
                            <span>Доступно обновление ${updateData.github_version}</span>
                        </div>
                        <button class="update-notification-close" onclick="updateNotificationSystem.dismissUpdate('${updateData.github_version}')">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>

                    <div class="update-notification-body">
                        <p class="current-version">
                            Текущая версия: <strong>${updateData.current_version}</strong> 
                            → Новая версия: <strong>${updateData.github_version}</strong>
                        </p>

                        ${changelogHtml ? `
                            <div class="update-changelog">
                                <details>
                                    <summary>📋 Что изменилось?</summary>
                                    <div class="changelog-content">
                                        ${changelogHtml}
                                    </div>
                                </details>
                            </div>
                        ` : ''}
                    </div>

                    <div class="update-notification-actions">
                        <button class="btn btn-primary btn-sm update-btn-now" 
                                onclick="updateNotificationSystem.updateNow()"
                                ${isAdmin ? '' : 'disabled'}>
                            <i class="fas fa-sync-alt"></i> Обновить сейчас
                        </button>
                        <button class="btn btn-secondary btn-sm update-btn-later" 
                                onclick="updateNotificationSystem.dismissUpdate('${updateData.github_version}')">
                            <i class="fas fa-clock"></i> Напомнить позже
                        </button>
                    </div>
                </div>
            </div>
        `;

        // Добавляем уведомление в начало body
        document.body.insertAdjacentHTML('afterbegin', notificationHtml);

        // Добавляем стили, если их еще нет
        this._addStyles();

        // Показываем уведомление
        const container = document.getElementById('update-notification-container');
        setTimeout(() => {
            container.classList.add('show');
        }, 100);
    }

    /**
     * Обновляет приложение
     */
    async updateNow() {
        if (!confirm('Приложение будет обновлено и перезагружено. Продолжить?')) {
            return;
        }

        try {
            const updateBtn = document.querySelector('.update-btn-now');
            updateBtn.disabled = true;
            updateBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Обновление...';

            const response = await fetch('/api/update-application', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            const data = await response.json();

            if (data.success) {
                alert('✅ Обновление успешно установлено!\n\nПриложение будет перезагружено...');
                // Перезагружаем страницу
                setTimeout(() => {
                    location.reload();
                }, 2000);
            } else {
                alert('❌ Ошибка при обновлении: ' + (data.message || data.error));
                updateBtn.disabled = false;
                updateBtn.innerHTML = '<i class="fas fa-sync-alt"></i> Обновить сейчас';
            }
        } catch (error) {
            console.error('Ошибка при обновлении:', error);
            alert('❌ Ошибка при обновлении приложения');
            const updateBtn = document.querySelector('.update-btn-now');
            updateBtn.disabled = false;
            updateBtn.innerHTML = '<i class="fas fa-sync-alt"></i> Обновить сейчас';
        }
    }

    /**
     * Отклоняет уведомление об обновлении
     */
    dismissUpdate(version) {
        // Сохраняем отклоненное обновление
        this._saveDismissedUpdate(version);

        // Удаляем уведомление с анимацией
        const container = document.getElementById('update-notification-container');
        if (container) {
            container.classList.remove('show');
            setTimeout(() => {
                container.remove();
            }, 300);
        }
    }

    /**
     * Форматирует changelog для отображения
     */
    _formatChangelog(changelog) {
        if (!changelog) return '';

        // Преобразуем markdown в HTML
        let html = changelog
            .replace(/^## (.+)$/gm, '<h6>$1</h6>')
            .replace(/^### (.+)$/gm, '<h7>$1</h7>')
            .replace(/^- (.+)$/gm, '<li>$1</li>')
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.+?)\*/g, '<em>$1</em>')
            .replace(/<li>(.+?)<\/li>/gs, (match) => {
                const items = match.match(/<li>(.+?)<\/li>/g);
                return '<ul>' + items.join('') + '</ul>';
            })
            .replace(/\n/g, '<br>');

        return html;
    }

    /**
     * Загружает список отклоненных обновлений из localStorage
     */
    _loadDismissedUpdates() {
        const stored = localStorage.getItem('dismissedUpdates');
        return stored ? JSON.parse(stored) : [];
    }

    /**
     * Сохраняет отклоненное обновление
     */
    _saveDismissedUpdate(version) {
        if (!this.dismissedUpdates.includes(version)) {
            this.dismissedUpdates.push(version);
            localStorage.setItem('dismissedUpdates', JSON.stringify(this.dismissedUpdates));
        }
    }

    /**
     * Проверяет, было ли обновление отклонено
     */
    _isUpdateDismissed(version) {
        return this.dismissedUpdates.includes(version);
    }

    /**
     * Добавляет CSS стили для уведомления
     */
    _addStyles() {
        if (document.getElementById('update-notification-styles')) {
            return; // Стили уже добавлены
        }

        const style = document.createElement('style');
        style.id = 'update-notification-styles';
        style.textContent = `
            .update-notification-top {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 15px 20px;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
                z-index: 10000;
                transform: translateY(-100%);
                transition: transform 0.3s ease;
                border-bottom: 3px solid #764ba2;
            }

            .update-notification-top.show {
                transform: translateY(0);
            }

            .update-notification-content {
                max-width: 1200px;
                margin: 0 auto;
            }

            .update-notification-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 10px;
            }

            .update-notification-title {
                font-size: 16px;
                font-weight: 600;
                display: flex;
                align-items: center;
                gap: 10px;
            }

            .update-notification-title i {
                font-size: 18px;
                animation: pulse 2s infinite;
            }

            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.6; }
            }

            .update-notification-close {
                background: rgba(255, 255, 255, 0.2);
                border: none;
                color: white;
                width: 32px;
                height: 32px;
                border-radius: 50%;
                cursor: pointer;
                font-size: 18px;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: background 0.2s;
            }

            .update-notification-close:hover {
                background: rgba(255, 255, 255, 0.3);
            }

            .update-notification-body {
                margin-bottom: 12px;
            }

            .current-version {
                margin: 0 0 10px 0;
                font-size: 14px;
                opacity: 0.95;
            }

            .update-changelog {
                background: rgba(0, 0, 0, 0.1);
                border-radius: 4px;
                padding: 10px;
                margin: 10px 0;
                max-height: 150px;
                overflow-y: auto;
            }

            .update-changelog details {
                cursor: pointer;
            }

            .update-changelog summary {
                font-weight: 500;
                margin-bottom: 8px;
                user-select: none;
            }

            .changelog-content {
                font-size: 13px;
                line-height: 1.4;
                white-space: pre-wrap;
            }

            .changelog-content h6 {
                margin: 8px 0 4px 0;
                font-size: 13px;
            }

            .changelog-content ul {
                margin: 5px 0;
                padding-left: 20px;
            }

            .changelog-content li {
                margin: 2px 0;
            }

            .update-notification-actions {
                display: flex;
                gap: 10px;
                justify-content: flex-start;
            }

            .update-notification-actions .btn {
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                cursor: pointer;
                font-size: 13px;
                font-weight: 500;
                transition: all 0.2s;
                display: flex;
                align-items: center;
                gap: 6px;
            }

            .update-btn-now {
                background: white;
                color: #667eea;
            }

            .update-btn-now:hover:not(:disabled) {
                background: #f0f0f0;
                transform: scale(1.05);
            }

            .update-btn-now:disabled {
                opacity: 0.6;
                cursor: not-allowed;
            }

            .update-btn-later {
                background: rgba(255, 255, 255, 0.2);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.3);
            }

            .update-btn-later:hover {
                background: rgba(255, 255, 255, 0.3);
            }

            @media (max-width: 768px) {
                .update-notification-top {
                    padding: 10px;
                }

                .update-notification-header {
                    flex-direction: column;
                    align-items: flex-start;
                    gap: 10px;
                }

                .update-notification-close {
                    align-self: flex-end;
                }

                .update-notification-actions {
                    flex-direction: column;
                    width: 100%;
                }

                .update-notification-actions .btn {
                    width: 100%;
                    justify-content: center;
                }
            }
        `;

        document.head.appendChild(style);
    }
}

// Инициализируем систему обновлений когда документ готов
let updateNotificationSystem;
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        updateNotificationSystem = new UpdateNotificationSystem();
    });
} else {
    updateNotificationSystem = new UpdateNotificationSystem();
}
