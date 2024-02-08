function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                // Does this cookie string begin with the name we want?
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

function startNewChat(my_gender, search_gender, topic) {
    fetch('/chat/search', {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrftoken, 'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            my_gender: my_gender,
            search_gender: search_gender,
            topic: topic
        })
    })
        .then(response => response.json())
        .then(data => {
                if (data.status === 'success') {
                    console.log('Room ID:', data.room_id);
                    handleSearchResponse(data);
                } else {
                    console.error('Error:', data.message);
                }
            }
        );

    function handleSearchResponse(data) {
        if (data.room_id.length > 0) {
            window.location.href = '/chat/room/' + data.room_id;
        } else {
            alert("No room was found");
        }
    }
}

