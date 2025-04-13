// 全局变量
let myvad = null;
let audioContext = null;
let isProcessing = false;
let isVADPaused = false;
let waveBars = [];
let audioQueue = []; // 用于流式播放的音频队列
let isAudioPlaying = false; // 表示是否正在播放音频
let audioContext2 = null; // 用于流式播放的音频上下文
let sseConnection = null; // 用于流式连接

// API配置
const apiConfig = {
    apiUrl: window.location.origin, // 使用当前域名作为API的基础URL
    processingEndpoint: '/process_audio',
    streamEndpoint: '/stream_audio', // 新增流式处理端点
    useStream: true, // 默认启用流式处理
    debug: true
};

// 初始化页面元素
document.addEventListener('DOMContentLoaded', () => {
    waveBars = Array.from(document.querySelectorAll('.wave-bar'));
    updateWaveform(0); // 初始化为静音状态
    
    // 事件监听
    document.getElementById('startBtn').addEventListener('click', startConversation);
    document.getElementById('stopBtn').addEventListener('click', stopConversation);
    document.getElementById('clearHistoryBtn').addEventListener('click', clearChatHistory);
});

// 更新波形显示
function updateWaveform(level) {
    waveBars.forEach((bar, index) => {
        // 根据语音活动级别和条形位置计算高度
        const positionFactor = 1 - Math.abs(index - 4) / 4; // 中间条形更高
        const heightFactor = level * 0.8 + 0.2; // 确保最小高度
        const scale = positionFactor * heightFactor;
        bar.style.transform = `scaleY(${scale})`;
        
        // 根据高度调整颜色
        const colorValue = Math.min(255, 100 + scale * 155);
        bar.style.background = `linear-gradient(to top, 
            rgba(0, 255, 157, ${scale}), 
            rgba(0, 180, 255, ${scale}))`;
    });
}

// 模拟波形动画
function simulateWaveform() {
    let level = 0;
    const interval = setInterval(() => {
        if (isProcessing || isVADPaused) {
            level = Math.max(0, level - 0.05);
        } else {
            // 随机波动，模拟环境噪音
            level = Math.min(1, Math.max(0, level + (Math.random() - 0.5) * 0.2));
        }
        updateWaveform(level);
    }, 100);
    
    return interval;
}

let waveInterval = simulateWaveform();

// 将Blob转换为Base64
function blobToBase64(blob) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onloadend = () => {
            // 移除data URL前缀
            const base64 = reader.result.split(',')[1];
            resolve(base64);
        };
        reader.onerror = reject;
        reader.readAsDataURL(blob);
    });
}

// 将Float32Array转换为WAV格式
function float32ArrayToWav(audioData, sampleRate) {
    // WAV文件头的大小为44字节
    const headerSize = 44;
    // 每个采样点是16位(2字节)
    const bytesPerSample = 2;
    const dataSize = audioData.length * bytesPerSample;
    const buffer = new ArrayBuffer(headerSize + dataSize);
    const view = new DataView(buffer);
    
    // 写入WAV文件头
    // "RIFF"标识
    writeString(view, 0, 'RIFF');
    // 文件大小
    view.setUint32(4, 32 + dataSize, true);
    // "WAVE"标识
    writeString(view, 8, 'WAVE');
    // "fmt "子块标识
    writeString(view, 12, 'fmt ');
    // 子块大小(16表示PCM格式)
    view.setUint32(16, 16, true);
    // 音频格式(1表示PCM)
    view.setUint16(20, 1, true);
    // 通道数(1表示单声道)
    view.setUint16(22, 1, true);
    // 采样率
    view.setUint32(24, sampleRate, true);
    // 字节率 = 采样率 * 通道数 * 字节数/采样点
    view.setUint32(28, sampleRate * 1 * bytesPerSample, true);
    // 块对齐 = 通道数 * 字节数/采样点
    view.setUint16(32, 1 * bytesPerSample, true);
    // 每个采样点的位数
    view.setUint16(34, 8 * bytesPerSample, true);
    // "data"子块标识
    writeString(view, 36, 'data');
    // 音频数据大小
    view.setUint32(40, dataSize, true);
    
    // 写入音频数据
    // 将Float32Array转换为16位整数
    const volume = 0.8; // 避免可能的截断
    for (let i = 0; i < audioData.length; i++) {
        // 将[-1,1]范围的float32转换为[-32768,32767]范围的int16
        const sample = Math.max(-1, Math.min(1, audioData[i]));
        const int16Sample = Math.floor(sample * volume * 32767);
        view.setInt16(headerSize + i * bytesPerSample, int16Sample, true);
    }
    
    return buffer;
}

// 辅助函数：将字符串写入DataView
function writeString(view, offset, string) {
    for (let i = 0; i < string.length; i++) {
        view.setUint8(offset + i, string.charCodeAt(i));
    }
}

// 更新处理进度状态
function updateProcessingStatus(stage, progress = null) {
    // 阶段: 'recording', 'processing', 'sending', 'receiving', 'complete'
    const statusElement = document.getElementById('status');
    let statusText = '';
    
    switch(stage) {
        case 'recording':
            statusText = "正在录音...";
            updateWaveActivityLevel(0.6 + Math.random() * 0.4); // 高活跃度
            break;
        case 'processing':
            statusText = "正在处理音频...";
            updateWaveActivityLevel(0.3 + Math.random() * 0.2); // 中等活跃度
            break;
        case 'sending':
            statusText = "发送请求到服务器...";
            updateWaveActivityLevel(0.2 + Math.random() * 0.1); // 低活跃度
            break;
        case 'receiving':
            statusText = "接收服务器响应...";
            updateWaveActivityLevel(0.2 + Math.random() * 0.2); // 低到中等活跃度
            break;
        case 'complete':
            statusText = "处理完成";
            updateWaveActivityLevel(0); // 无活跃度
            break;
        case 'initializing':
            statusText = "正在初始化...";
            break;
        case 'stopping':
            statusText = "正在停止...";
            break;
        case 'stopped':
            statusText = "已停止";
            break;
        default:
            statusText = stage; // 如果提供了自定义文本
    }
    
    // 如果提供了进度信息
    if (progress !== null && typeof progress === 'number') {
        statusText += ` (${Math.round(progress * 100)}%)`;
    }
    
    updateStatus(statusText, stage);
}

// 更新波形活动水平
function updateWaveActivityLevel(level) {
    // 使波形显示与处理状态对应
    waveBars.forEach((bar, index) => {
        const delay = index * 50; // 创建波浪效果的延迟
        setTimeout(() => {
            // 添加一些随机性使动画更自然
            const randomFactor = 0.8 + Math.random() * 0.4;
            const adjustedLevel = level * randomFactor;
            const positionFactor = 1 - Math.abs(index - 4) / 4; // 中间条形更高
            const scale = positionFactor * adjustedLevel;
            
            bar.style.transform = `scaleY(${Math.max(0.1, scale)})`;
            
            // 根据状态调整颜色
            let color1, color2;
            if (level > 0.5) {
                // 录音状态 - 绿色到蓝色
                color1 = `0, 255, ${Math.round(157 * scale)}`;
                color2 = `0, ${Math.round(180 * scale)}, 255`;
            } else if (level > 0.2) {
                // 处理状态 - 黄色到橙色
                color1 = `255, ${Math.round(200 * scale)}, 0`;
                color2 = `255, ${Math.round(140 * scale)}, 0`;
            } else if (level > 0) {
                // 等待状态 - 蓝色到紫色
                color1 = `100, ${Math.round(100 * scale)}, 255`;
                color2 = `180, 0, ${Math.round(220 * scale)}`;
            } else {
                // 不活跃状态 - 灰色
                color1 = `100, 100, 100`;
                color2 = `50, 50, 50`;
            }
            
            bar.style.background = `linear-gradient(to top, 
                rgba(${color1}, ${scale}), 
                rgba(${color2}, ${scale}))`;
        }, delay);
    });
}

// 处理音频API请求
async function processAudio(audioData) {
    try {
        console.log("处理音频...", typeof audioData, audioData.length);
        
        if (!audioData || audioData.length === 0) {
            console.error("无效的音频数据");
            showError("无效的音频数据");
            return;
        }
        
        // 转换为WAV格式
        const wavBuffer = float32ArrayToWav(audioData, 16000);
        
        // 创建Blob并转换为base64
        const blob = new Blob([wavBuffer], { type: 'audio/wav' });
        const base64Audio = await blobToBase64(blob);
        
        // 更新UI状态
        updateStatus("处理中...", "processing");
        hideError(); // 清除任何显示的错误
        
        // 判断是使用流式请求还是常规请求
        if (apiConfig.useStream !== false) {
            // 使用流式请求
            return await streamAudio(base64Audio, 'wav');
        } else {
            // 使用常规请求
            // 发送API请求，并指定音频格式为wav
            const response = await fetch('/process_audio', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    audio_data: base64Audio,
                    audio_format: 'wav'
                }),
            });
            
            if (!response.ok) {
                const errorMsg = `服务器错误: ${response.status} ${response.statusText}`;
                showError(errorMsg);
                throw new Error(errorMsg);
            }
            
            const result = await response.json();
            addLog(`收到API响应: 文本长度: ${result.text.length} 字符`);
            
            if (result.audio) {
                addLog(`收到音频响应，大小: ${result.audio.length} 字符`);
            }
            
            return result;
        }
    } catch (error) {
        addLog(`处理音频请求出错: ${error.message}`);
        showError(`处理错误: ${error.message}`);
        if (error.name === 'AbortError') {
            throw new Error('请求超时');
        }
        throw error;
    }
}

// 流式处理音频
async function streamAudio(base64Audio, audioFormat = 'wav') {
    try {
        updateStatus("开始流式请求...", "processing");
        
        // 重置状态
        audioQueue = [];
        isAudioPlaying = false;
        let accumulatedText = '';
        
        // 清理之前可能存在的连接
        if (sseConnection) {
            sseConnection.close();
            sseConnection = null;
        }
        
        // 添加日志
        addLog("开始流式音频请求");
        
        // 创建响应读取器
        const response = await fetch(`${apiConfig.apiUrl}/stream_audio`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                audio_data: base64Audio,
                audio_format: audioFormat
            })
        });
        
        if (!response.ok) {
            const errorMsg = `流式请求错误: ${response.status} ${response.statusText}`;
            showError(errorMsg);
            throw new Error(errorMsg);
        }
        
        // 创建一个空的AI回复用于更新
        addConversation('ai', '');
        
        // 获取响应的reader
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        
        // 处理流式响应
        while (true) {
            const { done, value } = await reader.read();
            
            if (done) {
                addLog("流式读取完成");
                break;
            }
            
            // 解码接收到的数据
            const text = decoder.decode(value, { stream: true });
            buffer += text;
            
            // 处理缓冲区中的每个完整事件
            let eventEnd = buffer.indexOf('\n\n');
            while (eventEnd !== -1) {
                const eventText = buffer.substring(0, eventEnd);
                buffer = buffer.substring(eventEnd + 2);
                
                // 处理事件文本
                if (eventText.startsWith('data: ')) {
                    const eventData = eventText.substring(6);
                    try {
                        const data = JSON.parse(eventData);
                        
                        // 根据事件类型处理
                        switch (data.event) {
                            case 'text':
                                // 处理文本事件
                                accumulatedText += data.data;
                                // 更新UI中的文本
                                const textElem = document.querySelector('.ai-message:last-child .message-text');
                                if (textElem) {
                                    textElem.textContent = accumulatedText;
                                }
                                break;
                                
                            case 'audio':
                                // 处理音频事件，添加到队列
                                audioQueue.push(data.data);
                                
                                // 如果还没有开始播放，就开始播放
                                if (!isAudioPlaying) {
                                    await playNextInQueue();
                                }
                                break;
                                
                            case 'usage':
                                // 处理用量统计
                                addLog(`模型用量: 提示词 ${data.data.prompt_tokens}，回复 ${data.data.completion_tokens}，总计 ${data.data.total_tokens}`);
                                break;
                                
                            case 'error':
                                // 处理错误
                                showError(`流处理错误: ${data.data}`);
                                addLog(`流处理错误: ${data.data}`);
                                break;
                                
                            case 'done':
                                // 处理完成
                                addLog("流处理完成");
                                updateStatus("处理完成", "complete");
                                break;
                        }
                    } catch (e) {
                        addLog(`解析事件数据时出错: ${e.message}`);
                        console.error("解析事件数据时出错:", e, eventData);
                    }
                }
                
                // 查找下一个事件的结束位置
                eventEnd = buffer.indexOf('\n\n');
            }
        }
        
        // 更新状态
        updateStatus("流式处理完成", "complete");
        
        // 返回结果
        return {
            text: accumulatedText,
            audio: null // 已经通过流式播放了
        };
    } catch (error) {
        console.error("流式处理音频出错:", error);
        showError(`流式处理音频出错: ${error.message}`);
        addLog(`流式处理音频出错: ${error.message}`);
        return null;
    }
}

// 播放队列中的下一个音频
async function playNextInQueue() {
    if (audioQueue.length === 0) {
        isAudioPlaying = false;
        return;
    }
    
    isAudioPlaying = true;
    
    try {
        // 从队列中取出第一个音频
        const base64Audio = audioQueue.shift();
        
        // 播放这个音频
        await playStreamAudio(base64Audio);
        
        // 播放完成后继续播放下一个
        await playNextInQueue();
    } catch (error) {
        console.error("播放队列音频出错:", error);
        isAudioPlaying = false;
    }
}

// 播放单个流音频片段
async function playStreamAudio(base64Audio) {
    return new Promise((resolve, reject) => {
        try {
            // 创建音频上下文（如果还不存在）
            if (!audioContext2) {
                audioContext2 = new (window.AudioContext || window.webkitAudioContext)();
            }
            
            // 解码base64
            const binaryString = window.atob(base64Audio);
            const bytes = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
                bytes[i] = binaryString.charCodeAt(i);
            }
            
            // 解码音频数据
            audioContext2.decodeAudioData(
                bytes.buffer,
                (buffer) => {
                    // 创建音频源
                    const source = audioContext2.createBufferSource();
                    source.buffer = buffer;
                    source.connect(audioContext2.destination);
                    
                    // 监听播放完成事件
                    source.onended = () => {
                        resolve();
                    };
                    
                    // 开始播放
                    source.start(0);
                },
                (error) => {
                    console.error("解码音频数据出错:", error);
                    reject(error);
                }
            );
        } catch (error) {
            console.error("播放音频片段出错:", error);
            reject(error);
        }
    });
}

// 播放Base64编码的音频
function playAudio(base64Audio) {
    return new Promise((resolve, reject) => {
        try {
            // 检测是否为iOS设备
            const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
            addLog(`当前设备: ${isIOS ? 'iOS' : '非iOS'}`);
            
            if (isIOS) {
                // iOS设备特殊处理 - 使用可见的音频控件
                addLog("iOS设备，使用特殊播放模式");
                
                // 获取iOS专用播放器元素
                const iosPlayerContainer = document.getElementById('iosAudioPlayer');
                const iosAudio = document.getElementById('iosAudio');
                
                if (!iosPlayerContainer || !iosAudio) {
                    addLog("警告: 未找到iOS音频播放器元素");
                    resolve(); // 继续流程
                    return;
                }
                
                // 显示播放器
                iosPlayerContainer.style.display = 'block';
                
                // 设置音频源
                iosAudio.src = `data:audio/wav;base64,${base64Audio}`;
                
                // 添加事件监听
                iosAudio.onended = () => {
                    addLog("iOS音频播放完成");
                    // 隐藏播放器
                    iosPlayerContainer.style.display = 'none';
                    resolve();
                };
                
                iosAudio.onerror = (e) => {
                    addLog(`iOS音频播放错误: ${e.message || '未知错误'}`);
                    // 隐藏播放器
                    iosPlayerContainer.style.display = 'none';
                    
                    // 尝试使用系统TTS作为备选方案
                    addLog("尝试使用系统TTS作为备选方案...");
                    // 简单消息告知用户
                    addConversation('system', '(iOS设备无法播放音频，请检查浏览器权限设置并允许自动播放，或点击"清除历史"按钮后重试)');
                    resolve();
                };
                
                // 模拟用户交互触发播放
                addLog("iOS音频已准备，请点击播放按钮");
                
            } else {
                // 非iOS设备使用原有方法
                const audio = new Audio();
                
                // 监听播放结束事件
                audio.addEventListener('ended', () => {
                    addLog("音频播放完成");
                    resolve();
                });
                audio.addEventListener('error', (e) => {
                    addLog(`音频播放错误: ${e.message}`);
                    reject(e);
                });
                
                // 设置音频源
                audio.src = `data:audio/wav;base64,${base64Audio}`;
                
                // 播放音频
                audio.play().catch(e => {
                    addLog(`播放音频失败: ${e.message}`);
                    reject(e);
                });
            }
        } catch (error) {
            addLog(`音频播放设置失败: ${error.message}`);
            reject(error);
        }
    });
}

// 初始化VAD
async function initVAD() {
    try {
        myvad = await vad.MicVAD.new({
            onSpeechStart: () => {
                if (!isProcessing && !isVADPaused) {
                    updateStatus("正在聆听...", "listening");
                    addLog("检测到语音开始");
                    
                    // 激活波形显示
                    waveBars.forEach(bar => {
                        bar.style.animationPlayState = 'running';
                    });
                }
            },
            onSpeechEnd: async (audio) => {
                if (isProcessing || isVADPaused) return;
                isProcessing = true;
                updateProcessingStatus('recording');
                addLog("检测到语音结束");
                
                // 记录audio对象类型，以便调试
                console.log("VAD音频数据:", audio);
                if (audio) {
                    addLog(`音频数据类型: ${audio.constructor.name}, 长度: ${audio.length || 0}`);
                } else {
                    addLog("警告: 收到空的音频数据");
                }
                
                // 显示正在输入指示器
                showTypingIndicator();
                
                // 暂停VAD而不是停止
                try {
                    if (myvad && typeof myvad.pause === 'function') {
                        await myvad.pause();
                        isVADPaused = true;
                        addLog("VAD已暂停");
                    }
                } catch (e) {
                    console.error("暂停VAD时出错:", e);
                    addLog(`错误: 暂停VAD失败 - ${e.message}`);
                }
                
                // 最大重试次数
                const maxRetries = 2;
                let retryCount = 0;
                let success = false;
                
                while (retryCount <= maxRetries && !success) {
                    try {
                        // 确认我们有有效的音频数据
                        if (!audio || !(audio instanceof Float32Array || Array.isArray(audio))) {
                            throw new Error("无法获取有效的音频数据");
                        }
                        
                        // 如果是重试，显示提示
                        if (retryCount > 0) {
                            addLog(`正在重试处理音频... (第${retryCount}次)`);
                            updateProcessingStatus(`重试处理... (${retryCount}/${maxRetries})`, retryCount/maxRetries);
                        }
                        
                        // 添加简单的用户消息，因为VAD不提供转写
                        if (retryCount === 0) {
                            addConversation('user', '(已检测到语音)');
                        }
                        
                        // 直接处理Float32Array音频数据
                        const result = await processAudio(audio);
                        
                        // 隐藏正在输入指示器
                        hideTypingIndicator();
                        
                        // 添加AI响应到对话
                        addConversation('ai', result.text);
                        
                        // 如果有音频响应，播放它
                        if (result.audio) {
                            updateProcessingStatus('speaking');
                            await playAIResponse(result.audio);
                        } else {
                            // 如果没有音频，使用浏览器的TTS
                            updateProcessingStatus('speaking');
                            await playTextAudio(result.text);
                            updateProcessingStatus('complete');
                        }
                        
                        // 标记成功
                        success = true;
                        
                    } catch (error) {
                        retryCount++;
                        console.error(`处理音频时出错 (尝试 ${retryCount}/${maxRetries}):`, error);
                        addLog(`错误: ${error.message}`);
                        
                        if (retryCount > maxRetries) {
                            hideTypingIndicator();
                            addConversation('ai', "很抱歉，处理您的请求时遇到问题。请再试一次或检查您的网络连接。");
                            showError(`处理失败，已尝试 ${maxRetries} 次: ${error.message}`);
                            updateProcessingStatus('error');
                        } else {
                            // 短暂延迟后重试
                            updateProcessingStatus('retrying', retryCount/maxRetries);
                            await new Promise(resolve => setTimeout(resolve, 1000));
                        }
                    }
                }
                
                // 播放完成后恢复VAD
                resumeVAD();
            },
            // 其他VAD配置参数
            positiveSpeechThreshold: 0.70,
            negativeSpeechThreshold: 0.50,
            model: "v5",
        });
        
        // 启动VAD
        await myvad.start();
        isVADPaused = false;
        addLog("VAD已启动");
    } catch (error) {
        console.error("VAD初始化失败:", error);
        addLog(`错误: VAD初始化失败 - ${error.message}`);
    }
}

// 显示正在输入指示器
function showTypingIndicator() {
    const conversationContent = document.getElementById('conversationContent');
    const typingDiv = document.createElement('div');
    typingDiv.className = 'typing-indicator';
    typingDiv.id = 'typingIndicator';
    
    for (let i = 0; i < 3; i++) {
        const dot = document.createElement('div');
        dot.className = 'typing-dot';
        typingDiv.appendChild(dot);
    }
    
    conversationContent.appendChild(typingDiv);
    conversationContent.scrollTop = conversationContent.scrollHeight;
}

// 隐藏正在输入指示器
function hideTypingIndicator() {
    const typingIndicator = document.getElementById('typingIndicator');
    if (typingIndicator) {
        typingIndicator.remove();
    }
}

// 恢复VAD监听
async function resumeVAD() {
    if (!myvad || !isVADPaused) return;
    try {
        // 某些VAD实现可能需要重新初始化而不是简单的start
        if (typeof myvad.start === 'function') {
            await myvad.start();
            isVADPaused = false;
            isProcessing = false;
            updateProcessingStatus('listening');
            addLog("VAD已恢复");
        }
    } catch (e) {
        console.error("恢复VAD时出错:", e);
        addLog(`错误: 恢复VAD失败 - ${e.message}`);
      
        // 失败时尝试重新初始化
        await initVAD();
    }
}

// 播放AI响应从服务器返回的音频
async function playAIResponse(base64Audio) {
    updateProcessingStatus('speaking');
    addLog("开始播放AI响应音频");
    
    // 模拟波形活动
    let speakingInterval = setInterval(() => {
        const level = 0.5 + Math.random() * 0.5;
        updateWaveActivityLevel(level);
    }, 100);
    
    try {
        await playAudio(base64Audio);
        addLog("AI响应音频播放完成");
    } catch (error) {
        addLog(`播放音频失败: ${error.message}`);
    } finally {
        clearInterval(speakingInterval);
        updateWaveActivityLevel(0);
        updateProcessingStatus('listening');
    }
}

// 使用浏览器的语音合成播放文本
async function playTextAudio(text) {
    addLog("使用浏览器语音合成播放文本");
    
    // 检测是否为iOS设备
    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
    
    // 模拟波形活动
    let speakingInterval = setInterval(() => {
        const level = 0.5 + Math.random() * 0.5;
        updateWaveActivityLevel(level);
    }, 100);
    
    return new Promise((resolve) => {
        if ('speechSynthesis' in window) {
            const utterance = new SpeechSynthesisUtterance(text);
            
            // 设置声音参数
            utterance.volume = 1.0;
            utterance.rate = 1.0;
            utterance.pitch = 1.0;
            utterance.lang = 'zh-CN';
            
            utterance.onstart = () => {
                addLog(`语音合成开始播放 (${isIOS ? 'iOS' : '非iOS'}设备)`);
            };
            
            utterance.onend = () => {
                clearInterval(speakingInterval);
                updateWaveActivityLevel(0);
                addLog("AI响应播放完成");
                resolve();
            };
            
            utterance.onerror = (event) => {
                addLog(`语音合成错误: ${event.error}`);
                clearInterval(speakingInterval);
                updateWaveActivityLevel(0);
                resolve();
            };
            
            // 在iOS上，需要特殊处理
            if (isIOS) {
                addLog("iOS设备，使用特殊TTS处理");
                
                // 取消任何正在进行的合成
                window.speechSynthesis.cancel();
                
                // 使用定时器延迟执行，避免iOS的限制
                setTimeout(() => {
                    try {
                        // 直接播放短文本
                        window.speechSynthesis.speak(utterance);
                        
                        // 由于iOS上长文本可能被截断，我们需要分段播放
                        if (text.length > 100) {
                            addLog("iOS上检测到长文本，使用分段播放");
                            
                            // 分段播放长文本的处理在这里添加
                            // (可根据需求进一步实现)
                            
                            // iOS Safari需要保持语音合成活跃
                            const iosInterval = setInterval(() => {
                                if (!window.speechSynthesis.speaking) {
                                    clearInterval(iosInterval);
                                    return;
                                }
                                // 暂停再恢复可以防止iOS上的截断问题
                                window.speechSynthesis.pause();
                                setTimeout(() => window.speechSynthesis.resume(), 50);
                            }, 5000);
                        }
                    } catch (e) {
                        addLog(`iOS语音合成异常: ${e.message}`);
                        clearInterval(speakingInterval);
                        updateWaveActivityLevel(0);
                        resolve();
                    }
                }, 300); // 延迟300ms执行
                
            } else {
                // 非iOS设备的处理
                try {
                    // 在非iOS设备上直接调用
                    window.speechSynthesis.cancel(); // 取消任何现有的语音
                    window.speechSynthesis.speak(utterance);
                } catch (e) {
                    addLog(`语音合成异常: ${e.message}`);
                    clearInterval(speakingInterval);
                    updateWaveActivityLevel(0);
                    resolve();
                }
            }
        } else {
            addLog("没有语音合成API");
            // 如果没有语音合成API，模拟延迟
            setTimeout(() => {
                clearInterval(speakingInterval);
                updateWaveActivityLevel(0);
                resolve();
            }, 2000);
        }
    });
}

// 启动对话
async function startConversation() {
    try {
        // 初始化音频上下文
        if (!audioContext) {
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
            addLog("音频上下文已初始化");
            
            // iOS需要在用户交互中解锁AudioContext
            if (audioContext.state === 'suspended') {
                audioContext.resume();
            }
        }
        
        // 初始化语音合成
        if ('speechSynthesis' in window) {
            // 在用户交互时预热语音合成引擎
            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance('');
            window.speechSynthesis.speak(utterance);
        }
        
        // 初始化状态显示
        updateProcessingStatus('initializing');
        
        // 初始化VAD
        await initVAD();
        
        // 更新UI状态
        document.getElementById('startBtn').disabled = true;
        document.getElementById('stopBtn').disabled = false;
        updateProcessingStatus('listening');
        
        // 添加欢迎消息
        addConversation('ai', '您好！我是智能语音助手，请开始说话...');
    } catch (error) {
        console.error("启动失败:", error);
        addLog(`错误: ${error.message}`);
        updateProcessingStatus('error');
        showError(`启动失败: ${error.message}`);
    }
}

// 停止对话
async function stopConversation() {
    try {
        updateProcessingStatus('stopping');
        
        if (myvad) {
            // 不同VAD实现可能有不同方法
            if (typeof myvad.destroy === 'function') {
                await myvad.destroy();
            } else if (typeof myvad.stop === 'function') {
                await myvad.stop();
            }
            addLog("VAD已停止");
        }
        
        if (audioContext && audioContext.state !== 'closed') {
            await audioContext.close();
            addLog("音频上下文已关闭");
        }
        
        // 重置状态
        myvad = null;
        audioContext = null;
        isProcessing = false;
        isVADPaused = false;
        
        // 更新UI
        document.getElementById('startBtn').disabled = false;
        document.getElementById('stopBtn').disabled = true;
        updateProcessingStatus('stopped');
        
        // 添加结束消息
        addConversation('ai', '对话已结束。如需继续，请点击"启动对话"按钮。');
    } catch (error) {
        console.error("停止时出错:", error);
        addLog(`错误: ${error.message}`);
        showError(`停止失败: ${error.message}`);
    }
}

// 更新状态显示
function updateStatus(text, state) {
    const statusElement = document.getElementById('status');
    const indicator = document.getElementById('statusIndicator');
    
    statusElement.textContent = text;
    
    // 移除所有状态类
    statusElement.className = 'status';
    indicator.className = 'status-indicator';
    
    // 添加新状态类
    if (state) {
        statusElement.classList.add(state);
        indicator.classList.add(state);
    }
}

// 添加日志条目
function addLog(message) {
    const logContent = document.getElementById('logContent');
    const now = new Date();
    const timeString = now.toLocaleTimeString();
    
    const logEntry = document.createElement('div');
    logEntry.className = 'log-entry';
    
    const timeSpan = document.createElement('span');
    timeSpan.className = 'log-time';
    timeSpan.textContent = timeString;
    
    const messageSpan = document.createElement('span');
    messageSpan.textContent = message;
    
    logEntry.appendChild(timeSpan);
    logEntry.appendChild(messageSpan);
    logContent.appendChild(logEntry);
    logContent.scrollTop = logContent.scrollHeight;
}

// 添加对话消息
function addConversation(speaker, message) {
    const conversationContent = document.getElementById('conversationContent');
    const messageDiv = document.createElement('div');
    messageDiv.className = speaker === 'user' ? 'user-message message' : 'ai-message message';
    
    const senderDiv = document.createElement('div');
    senderDiv.className = 'message-sender';
    senderDiv.textContent = speaker === 'user' ? '你说' : 'AI助手';
    
    const textDiv = document.createElement('div');
    textDiv.textContent = message;
    
    messageDiv.appendChild(senderDiv);
    messageDiv.appendChild(textDiv);
    conversationContent.appendChild(messageDiv);
    conversationContent.scrollTop = conversationContent.scrollHeight;
}

// 页面卸载时清理
window.addEventListener('beforeunload', () => {
    if (myvad || audioContext) {
        stopConversation();
    }
    if (waveInterval) {
        clearInterval(waveInterval);
    }
});

// 添加简单的错误处理函数
function hideError() {
    const errorElement = document.getElementById('errorMsg');
    if (errorElement) {
        errorElement.style.display = 'none';
        errorElement.textContent = '';
    }
}

function showError(message) {
    const errorElement = document.getElementById('errorMsg');
    if (errorElement) {
        errorElement.textContent = message;
        errorElement.style.display = 'block';
    } else {
        // 如果元素不存在，使用日志记录错误
        addLog(`错误: ${message}`);
    }
}

// 清除对话历史
async function clearChatHistory() {
    try {
        updateStatus("清除历史中...", "processing");
        
        // 发送清除历史的请求
        const response = await fetch('/clear_history', {
            method: 'POST'
        });
        
        if (!response.ok) {
            throw new Error(`HTTP错误! 状态: ${response.status}`);
        }
        
        const result = await response.json();
        addLog(`清除历史结果: ${result.message}`);
        
        // 清除界面上的对话记录
        const conversationContent = document.getElementById('conversationContent');
        conversationContent.innerHTML = '';
        
        // 添加系统消息
        addConversation('ai', '对话历史已清除，可以开始新的对话了。');
        
        updateStatus("历史已清除", "");
        setTimeout(() => updateStatus("等待语音输入...", "listening"), 1500);
        
    } catch (error) {
        console.error("清除历史时出错:", error);
        addLog(`错误: ${error.message}`);
        showError(`清除历史失败: ${error.message}`);
        updateStatus("清除历史失败", "error");
    }
} 