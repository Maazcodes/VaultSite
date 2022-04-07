/* global $ */

const modal = document.getElementById("myModal");
const span = document.getElementsByClassName("close")[0];

// When the user clicks on the button, open the modal
// eslint-disable-next-line no-unused-vars, camelcase
function show_modal() {
  modal.style.display = "block";
  document.querySelector("#modal-message").innerHTML = "";
  $("#collection_name").val("");
}

// When the user clicks on <span> (x), close the modal
if (span) {
  span.onclick = function () {
    modal.style.display = "none";
  };
}

// Closing modal on pressing escape key
$(document).keydown(function (event) {
  if (event.keyCode === 27) {
    span.click();
  }
});

// When the user clicks anywhere outside of the modal, close it
window.onclick = function (event) {
  if (event.target === modal) {
    modal.style.display = "none";
  }
};

const createCollectionForm = document.querySelector("#create_collection");
if (createCollectionForm) {
  createCollectionForm.addEventListener("submit", (event) => {
    event.preventDefault();

    document.querySelector("#modal-message").innerHTML = "";
    $("#create_collection_submit_btn").attr("disabled", true);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/vault/create_collection");

    const name = $("#collection_name").val();

    const data = new FormData();
    data.append("name", name);

    xhr.onloadend = function () {
      const response = JSON.parse(xhr.response);

      if (response["code"] === 1) {
        document.getElementById("modal-message").style.color = "green";
        document.querySelector("#modal-message").innerHTML =
          response["message"];
        $("#id_collection").append(new Option(name, response["collection_id"]));
        $("#id_collection").val(response["collection_id"]);
        setTimeout(function () {
          span.click();
        }, 500);
      } else {
        document.querySelector("#modal-message").innerHTML =
          response["message"];
        document.getElementById("modal-message").style.color = "red";
      }
      $("#create_collection_submit_btn").attr("disabled", false);
    };

    xhr.send(data);
  });
}
