// 秋日落叶生成器
document.addEventListener('DOMContentLoaded', function() {
    const autumnBackground = document.querySelector('.autumn-background');
    
    if (!autumnBackground) return;
    
    // 创建落叶
    function createLeaves(count) {
        for (let i = 0; i < count; i++) {
            const leaf = document.createElement('div');
            leaf.classList.add('leaf');
            
            // 随机位置
            const startX = Math.random() * 100;
            
            // 随机大小
            const size = 10 + Math.random() * 20;
            
            // 随机颜色（黄色到橙色）
            const hue = 30 + Math.random() * 30;
            const lightness = 40 + Math.random() * 20;
            
            // 随机动画时长
            const duration = 10 + Math.random() * 20;
            const delay = Math.random() * 20;
            
            // 设置样式
            leaf.style.left = `${startX}%`;
            leaf.style.width = `${size}px`;
            leaf.style.height = `${size}px`;
            leaf.style.background = `hsl(${hue}, 80%, ${lightness}%)`;
            leaf.style.animationDuration = `${duration}s`;
            leaf.style.animationDelay = `${delay}s`;
            
            // 随机旋转角度
            leaf.style.transform = `rotate(${Math.random() * 360}deg)`;
            
            // 添加叶子
            autumnBackground.appendChild(leaf);
        }
    }
    
    // 根据屏幕大小创建不同数量的叶子
    const createLeafCount = () => {
        const width = window.innerWidth;
        if (width < 768) {
            return 20;
        } else if (width < 1200) {
            return 40;
        } else {
            return 60;
        }
    };
    
    // 初始创建叶子
    createLeaves(createLeafCount());
    
    // 窗口大小改变时调整叶子数量
    let leafTimeout;
    window.addEventListener('resize', function() {
        clearTimeout(leafTimeout);
        leafTimeout = setTimeout(function() {
            // 移除现有叶子
            const leaves = document.querySelectorAll('.leaf');
            leaves.forEach(leaf => leaf.remove());
            
            // 创建新叶子
            createLeaves(createLeafCount());
        }, 500);
    });
    
    // 添加交互效果：点击创建更多叶子
    autumnBackground.addEventListener('click', function(e) {
        if (e.target === autumnBackground) {
            for (let i = 0; i < 5; i++) {
                const leaf = document.createElement('div');
                leaf.classList.add('leaf');
                
                const startX = (e.clientX / window.innerWidth) * 100;
                const size = 15 + Math.random() * 15;
                const hue = 30 + Math.random() * 30;
                
                leaf.style.left = `${startX}%`;
                leaf.style.top = `${e.clientY}px`;
                leaf.style.width = `${size}px`;
                leaf.style.height = `${size}px`;
                leaf.style.background = `hsl(${hue}, 80%, 50%)`;
                leaf.style.animationDuration = `${8 + Math.random() * 12}s`;
                leaf.style.animationDelay = '0s';
                
                autumnBackground.appendChild(leaf);
                
                // 动画结束后移除叶子
                setTimeout(() => {
                    if (leaf.parentNode) {
                        leaf.remove();
                    }
                }, 15000);
            }
        }
    });
});