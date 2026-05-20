/**
 * 食谱营养计算器 - 前端交互脚本
 */

(function() {
    'use strict';

    // ============================================================================
    // 初始化
    // ============================================================================

    document.addEventListener('DOMContentLoaded', function() {
        console.log('食谱营养计算器已加载');
        initAutoRefresh();
        initFormValidation();
        initSmoothScroll();
    });

    // ============================================================================
    // 自动刷新图表（每60秒）
    // ============================================================================

    function initAutoRefresh() {
        // 如果在首页，每60秒刷新一次图表
        if (document.querySelector('.hero-section')) {
            setInterval(function() {
                // 仅刷新图表图片，不刷新整个页面
                var chartImages = document.querySelectorAll('img[src*="static/charts"]');
                chartImages.forEach(function(img) {
                    var src = img.src.split('?')[0];
                    img.src = src + '?t=' + new Date().getTime();
                });
            }, 60000);
        }
    }

    // ============================================================================
    // 表单验证
    // ============================================================================

    function initFormValidation() {
        var forms = document.querySelectorAll('form');
        forms.forEach(function(form) {
            form.addEventListener('submit', function(e) {
                var inputs = form.querySelectorAll('input[required], textarea[required]');
                var valid = true;

                inputs.forEach(function(input) {
                    if (!input.value.trim()) {
                        input.classList.add('is-invalid');
                        valid = false;
                    } else {
                        input.classList.remove('is-invalid');
                        input.classList.add('is-valid');
                    }
                });

                if (!valid) {
                    e.preventDefault();
                    showToast('请填写必填项', 'warning');
                }
            });
        });
    }

    // ============================================================================
    // 平滑滚动
    // ============================================================================

    function initSmoothScroll() {
        var links = document.querySelectorAll('a[href^="#"]');
        links.forEach(function(link) {
            link.addEventListener('click', function(e) {
                var href = this.getAttribute('href');
                if (href === '#') return;
                var target = document.querySelector(href);
                if (target) {
                    e.preventDefault();
                    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            });
        });
    }

    // ============================================================================
    // Toast 通知
    // ============================================================================

    window.showToast = function(message, type) {
        if (type === undefined) type = 'info';
        var toastId = 'toast-' + Date.now();
        var bgClass = {
            'success': 'bg-success',
            'warning': 'bg-warning',
            'danger': 'bg-danger',
            'info': 'bg-info'
        }[type] || 'bg-info';

        var html = [
            '<div id="' + toastId + '" class="toast" role="alert" aria-live="assertive"',
            '     aria-atomic="true" style="position:fixed;top:80px;right:20px;z-index:9999;min-width:250px;">',
            '  <div class="toast-header ' + bgClass + ' text-white">',
            '    <strong class="me-auto">提示</strong>',
            '    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast"></button>',
            '  </div>',
            '  <div class="toast-body">' + message + '</div>',
            '</div>'
        ].join('');

        var container = document.createElement('div');
        container.innerHTML = html;
        document.body.appendChild(container);

        var toastEl = document.getElementById(toastId);
        var toast = new bootstrap.Toast(toastEl, { delay: 3000 });
        toast.show();

        toastEl.addEventListener('hidden.bs.toast', function() {
            toastEl.remove();
        });
    };

    // ============================================================================
    // API 请求辅助函数
    // ============================================================================

    window.api = {
        get: function(url, callback) {
            fetch(url)
                .then(function(response) { return response.json(); })
                .then(function(data) { callback(data); })
                .catch(function(error) {
                    console.error('API请求失败:', error);
                    showToast('网络请求失败', 'danger');
                });
        },

        post: function(url, data, callback) {
            fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            })
                .then(function(response) { return response.json(); })
                .then(function(data) { callback(data); })
                .catch(function(error) {
                    console.error('API请求失败:', error);
                    showToast('网络请求失败', 'danger');
                });
        }
    };

    // ============================================================================
    // 食谱推荐 API
    // ============================================================================

    window.recommendRecipes = function(ingredients, callback) {
        window.api.post('/api/recommend', {
            ingredients: ingredients,
            max_missing: 3
        }, callback);
    };

    // ============================================================================
    // 食材分析 API
    // ============================================================================

    window.analyzeIngredients = function(text, callback) {
        window.api.post('/api/analyze', {
            ingredients: text
        }, callback);
    };

    // ============================================================================
    // 膳食计划 API
    // ============================================================================

    window.generatePlan = function(days, targetCalories, callback) {
        window.api.post('/api/plan', {
            days: days || 7,
            target_calories: targetCalories || null
        }, callback);
    };

})();
