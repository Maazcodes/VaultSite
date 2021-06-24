// Get the modal
let modal = document.getElementById("myModal");

// Get the button that opens the modal
let btn = document.getElementById("myBtn");

// Get the <span> element that closes the modal
let span = document.getElementsByClassName("close")[0];

// When the user clicks on the button, open the modal
function show_modal() {
  modal.style.display = "block";
}

// When the user clicks on <span> (x), close the modal
span.onclick = function() {
  modal.style.display = "none";
}

// When the user clicks anywhere outside of the modal, close it
window.onclick = function(event) {
  if (event.target == modal) {
    modal.style.display = "none";
  }
}

const create_collection_form = document.querySelector('#create_collection')
create_collection_form.addEventListener('submit', event => {
    event.preventDefault();

    document.querySelector('#modal-message').innerHTML = '';
    $('#create_collection_submit_btn').attr("disabled", true);
    
    let xhr = new XMLHttpRequest();
    xhr.open('POST', '/vault/create_collection');

    let name = $('#collection_name').val();

    let data = new FormData();
    data.append('name', name);

    xhr.onloadend = function() {
      
      response = JSON.parse(xhr.response)
      
      if (response['code'] == 1) {
        document.getElementById("modal-message").style.color = 'green';
        document.querySelector('#modal-message').innerHTML = response['message'] + ' Page reloading in 5 seconds ...';
        setTimeout(function () {
          window.location.reload();
        }, 5000);
      }
      else {
        document.querySelector('#modal-message').innerHTML = response['message'];
        document.getElementById("modal-message").style.color = 'red';
      }
      $('#create_collection_submit_btn').attr("disabled", false);
    
    }
    
    xhr.send(data);
})
