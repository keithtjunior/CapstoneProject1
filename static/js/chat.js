$( document ).ready(function() {
    
    let socket = io.connect();

    socket.on('connect', () => {
        console.log("Connected to WS server");
        console.log('socket: ', socket.connected); 
    });
    
    socket.on('chat', (data) => {
        setMessage(data);
    });
    
    let messageInput = document.getElementById('messageInput');
    let messageBtn = document.getElementById('messageBtn');
    
    messageInput.addEventListener('keyup', (e) => {
        if (e.key == 'Enter') {
            sendServerData();
        }
    });
    
    messageBtn.addEventListener('click', (e) => {
        sendServerData();
    });
    
    const sendServerData = () => {
    
        let message = messageInput.value.trim();
        if (message == '') return false;
    
        let url = window.location.href;
        let id = url.split("/chats")[1][1];
        let thread = document.getElementById(`thread-${id}`);
    
        let thread_id = thread.getAttribute('data-thread-id');
        if (thread_id != id) return false;
    
        let thread_room = thread.getAttribute('data-thread-room');
        let user_id = thread.getAttribute('data-user-id');
        let current_user_id = thread.getAttribute('data-current-user-id');
    
        let data = {message, thread_id, thread_room, user_id, current_user_id};
    
        socket.emit('chat_message', JSON.stringify(data));
    }
    
    const setMessage = (data) => {
    
        let thread = document.getElementById(`thread-${data.thread_id}`);
        let current_user_id = thread.getAttribute('data-current-user-id');
    
        let lstMsgContainer = document.getElementById(`lastMessage-${data.thread_id}`);
        let chatTime = document.getElementById(`chatTime-${data.thread_id}`);
    
        let msgContainer = document.getElementById('messageContainer');
        let msgBody = document.getElementById('messageBody');
    
        msgContainer.innerHTML += `
            <div class='message ${data.message_author_id == current_user_id ? 'self' : ''}'>
                <div class='message-wrapper'>
                    <div class='message-content'>
                        ${data.message_author_id == current_user_id ? 
                            `<span class='translated-msg badge bg-light text-dark'>
                                ${data.message_language != data.translated_language ? `${data.translated_language}: <span class='translated-text'>${data.translated_text}</span>` : `${data.translated_language}`}
                            </span>` : 
                            `<span class='translated-msg badge bg-light text-dark'>
                                ${data.message_language != data.translated_language ? `${data.message_language}: <span class='translated-text'>${data.message_text}</span>` : `${data.message_language}`}
                            </span>`
                        }
                        <span class='original-msg'>
                            ${data.message_author_id == current_user_id ? 
                                `${data.message_text}` : `${data.translated_text}`}
                        </span>
                    </div>
                </div>
                <div class='message-options'>
                    <div class='avatar avatar-sm ${data.user_class_color}'>
                        <span>${data.user_first_name[0]} ${data.user_last_name[0]}</span>
                    </div>
                    <span class='message-date'>${data.message_time}</span>
                </div>
            </div>
        `;
    
        lstMsgContainer.innerText = data.message_text;
        chatTime.innerText = data.message_time;
    
        messageInput.value = '' 
        msgBody.scrollTop = msgBody.scrollHeight;
    }

});

