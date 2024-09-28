$( document ).ready(function() {

    let socket = io.connect();

    socket.on('connect', function() {
        console.log("Connected to WS server");
        console.log('socket: ', socket.connected); 
    });
    
    let localStream;
    let remoteStream;
    let peerConnection;
    
    const servers = {
        iceServers:[
            {
                urls: [
                    'stun:stun.l.google.com:19302',
                    'stun:stun.l.google.com:5349',               
                    'stun:stun1.l.google.com:3478',
                    'stun:stun1.l.google.com:5349',
                    'stun:stun2.l.google.com:19302',
                    'stun:stun2.l.google.com:5349',
                    'stun:stun3.l.google.com:3478',
                    'stun:stun3.l.google.com:5349',
                    'stun:stun4.l.google.com:19302',
                    'stun:stun4.l.google.com:5349'
                ]
            }
        ],
        iceCandidatePoolSize: 10
    }
    
    let constraints = {
        video:{
            width:{min:640, ideal:1920, max:1920},
            height:{min:480, ideal:1080, max:1080},
        },
        audio: { echoCancellation: true }
    }
    
    let getCallData = async () => {
    
        let videoCall = document.getElementById('video-container');
    
        let call_id = videoCall.getAttribute('data-call-id');
        let room_id = videoCall.getAttribute('data-room-id');
        let contact_id = videoCall.getAttribute('data-contact-id');
        let current_user_id = videoCall.getAttribute('data-current-user-id');
    
        return {call_id, room_id, contact_id, current_user_id}
    }
    
    const createPeerConnection = async (offer) => {
    
        if(offer)
            if (peerConnection) return;
    
        try {
            let data = await getCallData();
            peerConnection = new RTCPeerConnection(servers);
    
            peerConnection.onicecandidate = async (event) => {
                const message = {
                    type: "candidate",
                    candidate: null,
                    data
                };
                if(event.candidate){
                    message.candidate = event.candidate.candidate;
                    message.sdpMid = event.candidate.sdpMid;
                    message.sdpMLineIndex = event.candidate.sdpMLineIndex;
                    socket.emit("message", message);
                }
            }
    
            remoteStream = new MediaStream();
            document.getElementById('user-2').srcObject = remoteStream;
    
            peerConnection.ontrack = async (event) => {
                event.streams[0].getTracks().forEach((track) => {
                    remoteStream.addTrack(track);
                })
            }
    
            localStream.getTracks().forEach((track) => {
                peerConnection.addTrack(track, localStream);
            })
    
        } catch (err) {
            console.log(err);
        }
    }
    
    const createOffer = async () => {
        await createPeerConnection(null);
        let offer = await peerConnection.createOffer();
        socket.emit('message', { type: 'offer', sdp: offer.sdp });
        await peerConnection.setLocalDescription(offer);
    }
    
    const createAnswer = async (offer) => {
        await createPeerConnection(offer);
        await peerConnection.setRemoteDescription(offer);
        let answer = await peerConnection.createAnswer();
        socket.emit('message', { type: 'answer', sdp: answer.sdp });
        await peerConnection.setLocalDescription(answer);
    }
    
    const addAnswer = async (answer) => {
        if(!peerConnection) return;
        try {
            await peerConnection.setRemoteDescription(answer)
        } catch (err) {
            console.log(err);
        }
    }
    
    const handleCandidate = async (candidate) => {
        if(!peerConnection) return;
        try {
            await peerConnection.addIceCandidate(candidate)
        } catch (err) {
            console.log(err);
        }
    }
    
    const leaveChannel = async () => {
        if(peerConnection){
            await peerConnection.close();
            peerConnection = null;
        }
        if(localStream){
            await localStream.getTracks().forEach((track) => track.stop());
            localStream = null;
        }
        let data = await getCallData();
        socket.emit('message', { type: 'close', data });
    }
    
    const main = async () => {
        try {
            localStream = await navigator.mediaDevices.getUserMedia(constraints)
            document.getElementById('user-1').srcObject = localStream;
            let data = await getCallData();
            socket.emit('message', { type: 'ready', data }); 
        } catch (err) {
            console.log(err);
        }
    }

    // Video Chat App
    // https://dev.to/eyitayoitalt/develop-a-video-chat-app-with-webrtc-socketio-express-and-react-3jc4
    
    socket.on('message', (e) => {
    
        if (!localStream) return;
    
        switch (e.type) {
            case 'offer':
                createAnswer(e);
                break;
            case 'answer':
                addAnswer(e);
                break;
            case 'candidate':
                handleCandidate(e);
                break;
            case 'ready':
                if (peerConnection) return;
                createOffer();
                break;
            case 'close':
                console.log('Disconnected from WS server');
                break;
            default:
                console.log('unhandled', e);
                break;
        }
    });

    // Web RTC 
    // https://www.youtube.com/watch?v=QsH8FL0952k
    // https://github.com/divanov11/PeerChat
    
    let toggleCamera = async () => {
        let videoTrack = localStream.getTracks().find(track => track.kind === 'video')
    
        if(videoTrack.enabled){
            videoTrack.enabled = false
            document.getElementById('camera-btn').style.backgroundColor = '#ff337c'
        }else{
            videoTrack.enabled = true
            document.getElementById('camera-btn').style.backgroundColor = '#1cad82'
        }
    }
    
    let toggleMic = async () => {
        let audioTrack = localStream.getTracks().find(track => track.kind === 'audio')
    
        if(audioTrack.enabled){
            audioTrack.enabled = false
            document.getElementById('mic-btn').style.backgroundColor = '#ff337c'
        }else{
            audioTrack.enabled = true
            document.getElementById('mic-btn').style.backgroundColor = '#3c91ec'
        }
    }

    // Video app layout
    // https://codepen.io/mecies/embed/vYrvZGq?

    let videoContainer = document.getElementById('video-container');

    let mobileViewUpdate = async () => {
        let tiles = document.getElementsByClassName('video-tile');
        let viewportWidth = window.innerWidth;
        let tilesArray = [];
        let gapBetweenTiles;
        
        if ( viewportWidth <= 1200 ) {
            tilesArray = [...tiles];
            videoContainer.className = 'd-flex flex-column justify-content-center align-items-center';
            tilesArray.forEach((element) => {
                element.style.width = '100%';
            });
        } else {
            gapBetweenTiles = 5;
            tilesArray = [...tiles];
            let elementInARowCount = Math.ceil(Math.sqrt(tiles.length));
    
            videoContainer.className = '';
            videoContainer.style.gap = `${gapBetweenTiles}px`;
            
            tilesArray.forEach((element) => {
                element.style.width = `calc(calc(100% / ${elementInARowCount}) - ${gapBetweenTiles}px)`
            });
        }
    }
    
    if(videoContainer) {
        window.onload = mobileViewUpdate;
        window.onresize = mobileViewUpdate;
    }
    
    document.getElementById('leave-btn').addEventListener('click', leaveChannel)
    document.getElementById('camera-btn').addEventListener('click', toggleCamera)
    document.getElementById('mic-btn').addEventListener('click', toggleMic)

    main();

});

