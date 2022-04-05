/* global URLS, Flow, md5, $ */

function secondsToString(seconds) {
  var remaining_min = Math.floor(seconds / 60);
  var remaining_sec = seconds - remaining_min * 60;

  // For hours
  var remaining_hours = Math.floor(seconds / 3600);
  var total_remaining_sec_hr = seconds - remaining_hours * 3600; // Total remaining seconds after hours
  var remaining_seconds_after_mins = Math.floor(total_remaining_sec_hr / 60); // Converting remaining seconds into minutes to get remaining minutes
  var actual_remaining_sec = seconds - remaining_seconds_after_mins * 60; // Getting remaining seconds after minutes

  if (seconds <= 60) {
    return seconds + " s ";
  } else if (seconds > 60 && seconds <= 3600) {
    return remaining_min + " m " + remaining_sec + " s ";
  } else if (seconds > 3600) {
    return (
      remaining_hours +
      " h " +
      remaining_seconds_after_mins +
      " m " +
      actual_remaining_sec +
      " s "
    );
  }
}

const formatBytes = (bytes, decimals = 2) => {
  if (bytes === 0) return "0 Bytes";

  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = [
    "Bytes",
    "KiB",
    "MiB",
    "GiB",
    "TiB",
    "PiB",
    "EiB",
    "ZiB",
    "YiB",
  ];

  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + " " + sizes[i];
};

var flow = new Flow({
  target: URLS.api_flow_chunk,
  query: { upload_token: "my_token" },
  simultaneousUploads: 3,
  speedSmoothingFactor: 0.005,
  progressCallbacksInterval: 1000,
  maxChunkRetries: undefined,
  permanentErrors: [],
  chunkRetryInterval: 5000,
  allowDuplicateUploads: true,
  generateUniqueIdentifier: function (file) {
    var relativePath =
      file.relativePath ||
      file.webkitRelativePath ||
      file.fileName ||
      file.name;
    // overriding uniqueIdentifier function to ensure the identifier is consistent throughout flow.js internals
    const uniqueIdentifier = `${file.size}-${relativePath}`;
    const hashUniqueIdentifier = md5(uniqueIdentifier);
    return hashUniqueIdentifier;
  },
});

flow.assignBrowse(document.getElementById("uploadFilesButton"));
flow.assignBrowse(document.getElementById("uploadFoldersButton"), true);
flow.assignDrop(document.getElementById("dropTarget"));

let files = [];
let upload_size = 0;
let currentDepositId = undefined;
let files_dict = {};
let flowfile_objects_dict = {};

let flow_object_array = [];
flow.on("fileAdded", function (file, event) {
  let new_file = {
    flow_identifier: file.uniqueIdentifier,
    name: file.name,
    relative_path: file.relativePath,
    size: file.size,
    type: file.file.type,
    pre_deposit_modified_at: new Date(file.file.lastModified).toISOString(),
  };
  files.push(new_file);
  flowfile_objects_dict[String(file["relativePath"])] = file;
  // dictionary with relative path as key
  files_dict[String(new_file["relative_path"])] = new_file;
  upload_size += new_file["size"];
  document.querySelector("#dropTargetMsg").innerHTML =
    "<div>" +
    files.length +
    pluralizeWord(" file ", " files ", files.length) +
    " selected. Total Upload Size: " +
    formatBytes(upload_size) +
    "</div>";
});

flow.on("fileSuccess", function (file, message) {});

function pluralizeWord(singularWord, pluralWord, count) {
  return count != 1 ? pluralWord : singularWord;
}

flow.on("fileError", function (file, message) {
  console.log(file, message);
  btn = document.getElementById("flowPost");
  btn.innerHTML = "Upload";
  btn.disabled = false;
  document.querySelector("#flow-stats").innerHTML = "Error Uploading";
});

function changeStats() {
  if ($("#id_collection").find(":selected").val() != "") {
    document.querySelector("#dropTargetMsg").innerHTML =
      "<div>" +
      files.length +
      pluralizeWord(" file ", " files ", files.length) +
      " selected. Total Upload Size: " +
      formatBytes(upload_size) +
      "</div>";
  }
}

document
  .getElementById("id_collection")
  ?.addEventListener("change", changeStats);

function deposit_status(time) {
  if (currentDepositId == undefined) {
    console.error("Deposit Id not defined");
  }
  let xhr = new XMLHttpRequest();
  xhr.open("GET", `${URLS.api_deposit_status}?deposit_id=${currentDepositId}`);
  xhr.setRequestHeader("Content-Type", "application/json");
  xhr.send();
  xhr.onloadend = function () {
    if (xhr.status == 200) {
      res = JSON.parse(xhr.response);
      let processing =
        res["hashed_files"] + res["replicated_files"] + res["errored_files"];
      let message =
        "Processing Files: " +
        processing +
        "/" +
        res["total_files"] +
        ", Processing Queue: " +
        res["file_queue"] +
        '<div class="loader"></div>';
      document.querySelector("#flow-stats").innerHTML = message;
      if (processing < res["total_files"]) {
        setTimeout(function () {
          deposit_status(time + 1);
        }, 1000);
      } else {
        document.getElementById("progress_bar_flow").innerHTML = "";
        document.querySelector("#flow-stats").innerHTML = "Upload Complete";
      }
    } else if (xhr.status == 400) {
      console.error("Deposit Error: No Deposit ID");
      document.querySelector("#flow-stats").innerHTML =
        "Deposit Error: No Deposit ID";
    } else if (xhr.status == 404) {
      console.error("Deposit Error: No Deposit for ID");
      document.querySelector("#flow-stats").innerHTML =
        "Deposit Error: No Deposit for ID";
    } else {
      console.error("API Error: Cannot Fetch Status of API");
      setTimeout(function () {
        console.log("Calling deposit_status again");
        deposit_status(time + 1);
      }, 1000);
      document.querySelector("#flow-stats").innerHTML =
        "API Error: Cannot Fetch Deposit Status";
      return;
    }
  };
}

flow.on("complete", function () {
  document.querySelector("#flow-stats").innerHTML = "Upload Complete";
  btn = document.getElementById("flowPost");
  btn.innerHTML = "Upload";
  btn.disabled = false;
  files = [];
  upload_size = 0;
  document.querySelector("#progress_bar_flow").style.display = "none";
  deposit_status(0);
});

let initial_time = 0;
let sum_speed = 0;
let counter = 0;
flow.on("progress", function () {
  if (counter == 0) {
    initial_time = Date.now();
    counter++;
    return;
  }
  counter++;
  let uploaded_size = flow.sizeUploaded();
  let passed_time = Date.now() - initial_time;
  let speed = uploaded_size / passed_time;
  sum_speed += speed;
  avg_speed = sum_speed / counter;
  let total_file_size = flow.getSize();
  let time_remaining = (total_file_size - uploaded_size) / avg_speed;
  document.querySelector("#flow-stats").innerHTML =
    "Uploading Files (" +
    " Time left: " +
    secondsToString(Math.floor(time_remaining / 1000)) +
    ") ";
  document.querySelector("#progress_bar_flow").value = flow.progress() * 100;
});

let warning_tag = document.getElementById("warning");

let warningheader = document.getElementById("warningHeader");

function start_deposit(flow, files) {
  if ($("#id_collection").find(":selected").val() == "") {
    document.querySelector("#flow-stats").innerHTML =
      "<b>Please select a collection</b>";
    return;
  }

  if (files.length === 0) {
    document.querySelector("#flow-stats").innerHTML =
      "<b>Please select files/folders to upload.</b>";
    return;
  }

  document.querySelector("#progress_bar_flow").value = flow.progress() * 0;
  let coll_input = document.getElementById("id_collection");
  let collection_id = coll_input?.options[coll_input.selectedIndex].value;

  btn = document.getElementById("flowPost");
  btn.innerHTML = "Uploading...";
  btn.disabled = true;

  let xhr = new XMLHttpRequest();

  xhr.open("POST", URLS.api_warning_deposit, true);
  xhr.setRequestHeader("Content-Type", "application/json");
  let payload = {
    collection_id: collection_id,
    files: files,
    total_size: upload_size,
    parent_node_id: PARENT_NODE_ID || null,
  };
  xhr.send(JSON.stringify(payload));
  xhr.onloadend = function () {
    if (xhr.status == 200) {
      response = JSON.parse(xhr.response);
      let objects_list = response["objects"]; // All matched files
      let path_list = response["relative_path"];
      const files_list = [];
      const paths = [];
      for (let index = 0; index < objects_list.length; index++) {
        let element = objects_list[index];
        let file_name = element["name"];
        files_list.push(file_name);
      }

      for (let index = 0; index < path_list.length; index++) {
        let path_element = path_list[index];
        paths.push(path_element);
      }

      if (files_list.length > 0) {
        overlappedFiles(files_list, false);
      } else if (paths.length > 0) {
        overlappedFiles(paths, false);
      } else {
        registerDeposit(files);
      }

      // reversing all the actions after clicking outside the window and again on upload button
      SkipreplaceBtns = $(".skipreplace");
      for (let index = 0; index < SkipreplaceBtns.length; index++) {
        const button = SkipreplaceBtns[index];
        if (button.disabled) {
          button.disabled = false;
        }
        if (!$(button).parent().hasClass("path-not-selected")) {
          $(button).parent().addClass("path-not-selected");
        }
      }
    }
  };
}

function replaceClass(skip_or_replace_element) {
  if (skip_or_replace_element.hasClass("path-not-selected")) {
    skip_or_replace_element.removeClass("path-not-selected");
    skip_or_replace_element.addClass("path-selected");
  }
}

skip_path_array = [];

skip_replace_id_dict = {};

// Start of warning function

function overlappedFiles(overlapped_files_list, confirm_button_status) {
  // Get the modal
  let warning_modal = document.getElementById("warningModal_id");

  // When the user clicks on the button, open the modal
  warning_modal.style.display = "block";

  // Skip All and Replace All Buttons
  warningheader.innerHTML =
    "<br>" +
    '<button class="button small skipBtn" id="skipall" style = "margin-right: 10px; margin-left: 10px; border-radius: 20px; padding: 10px 20px 10px 20px;"> Skip All </button><button class="button small replaceBtn" id="replaceall" style = "border-radius: 20px; padding: 10px 20px 10px 20px;"> Replace All</button>' +
    `<div id = "files_count" style = "font-style: italic; margin-bottom: 20px;"><b>Remaining files to make skip/replace selection: </b>${overlapped_files_list.length} </div>`;

  // Adding Confirm button before all rows
  warningheader.innerHTML += `<br><button class="confirm-button"> Confirm </button><div id="confirmBtn1text"></div><br><br>`;

  for (let index = 0; index < overlapped_files_list.length; index++) {
    let file_element = overlapped_files_list[index];

    // Adding Skip and Replace buttons after every matched path
    warningheader.innerHTML +=
      '<div class="path-not-selected" id="' +
      String(index) +
      '" style = " margin-bottom: 0px; display: flex; box-sizing: border-box; flex-wrap: wrap; height: 32px; vertical-align: middle;">' +
      '<div style="margin-top: 7px; height: 42px; display:inline-block; box-sizing: border-box; flex: 60%; max-width: 500px; left: 0px; text-align: left; vertical-align: middle;" id = "text" >' +
      file_element +
      "</div>" +
      '<button class="button small skip-button skipreplace skipBtn " style = "border-radius: 20px; right: -190px; height: 36px; padding: 7px 15px 7px 15px; position: relative;"> Skip </button><button class="button small replace-button skipreplace replaceBtn " style = "border-radius: 20px; height: 36px; right: -200px; padding: 7px 15px 7px 15px; margin-right: 0px;"> Replace </button></div><hr>';
  }

  // Adding another Confirm button after all rows
  warningheader.innerHTML += `<br><button class="confirm-button"> Confirm </button>`;

  if (confirm_button_status) {
    // displaying the message if no action is performed on all the paths
    document.getElementById("confirmBtn1text").innerHTML =
      "<b>Please select skip or replace on all files</b>";
    warningheader.innerHTML +=
      "<div><b>Please select skip or replace on all files</b></div>";

    // Changing the text after clicking on confirm button
    document.getElementById("skipall").innerHTML = "Skip Remaining";
    document.getElementById("replaceall").innerHTML = "Replace Remaining";

    // maintaining all the previous actions after clicking on confirm button
    for (var key in skip_replace_id_dict) {
      // here key is id and value is skip or replace
      // getting skip and replace elements from the same id
      skip_element = $("#" + key)[0].childNodes[1];
      replaceElement = $("#" + key)[0].childNodes[2];

      value = skip_replace_id_dict[key];
      if (value == "skip") {
        skip_element.disabled = true;
      } else {
        replaceElement.disabled = true;
      }

      // removing this class to remove the element from path-not-selected list
      $("#" + key).removeClass("path-not-selected");
    }

    not_selected_paths = document.querySelectorAll(".path-not-selected");
    document.getElementById("files_count").innerHTML =
      "<b>Remaining files to make skip/replace selection: </b>" +
      not_selected_paths.length;
  }

  // collecting both the confirm buttons to add event listeners
  confirm_buttons = document.querySelectorAll(".confirm-button");
  confirm_buttons.forEach(function (button) {
    button.addEventListener("click", function () {
      not_selected_paths = document.querySelectorAll(".path-not-selected");
      // if no action is performed on all paths, repeat the same function with previous changes
      if (not_selected_paths.length > 0) {
        // setting confirm button status as true after the user clicks on confirm button
        overlappedFiles(overlapped_files_list, true);
      } else {
        warning_modal.style.display = "none";

        for (let index = 0; index < skip_path_array.length; index++) {
          const path = skip_path_array[index];
          // Removing the skipped file from upload queue by relative path
          flow.removeFile(flowfile_objects_dict[path]);

          // Deleting elements from dictionary by relative path
          delete files_dict[path];
        }

        let final_deposit_list = Object.values(files_dict);
        registerDeposit(final_deposit_list);
      }
    });
  });

  // Skip All Button
  SkipAllBtn = document.getElementById("skipall");
  ReplaceAllBtn = document.getElementById("replaceall");
  SkipAllBtn.onclick = function () {
    SkipAllBtn.style.backgroundColor = "darkgreen";
    not_selected_elements = $(".path-not-selected");
    for (let index = 0; index < not_selected_elements.length; index++) {
      let parent_element = not_selected_elements[index];
      file_path = parent_element.childNodes[0].innerText;
      // appending skip path array with the file path
      skip_path_array.push(file_path);
      // Disable all not selected skip buttons after clicking on Skip All/Skip remaining button
      parent_element.childNodes[1].disabled = true;
      // Replacing the class by path-selected
      $(parent_element).removeClass("path-not-selected");
      $(parent_element).addClass("path-selected");
    }

    document.getElementById("files_count").innerHTML =
      "<b>Remaining files to make skip/replace selection: </b>" + 0;
  };

  // Replace All Button
  ReplaceAllBtn.onclick = function () {
    ReplaceAllBtn.style.backgroundColor = "red";
    // Disable all replace buttons after clicking on Replace All button
    not_selected_elements = $(".path-not-selected");
    for (let index = 0; index < not_selected_elements.length; index++) {
      let parent_element = not_selected_elements[index];
      // Disable all not selected replace buttons after clicking on Replace All/Replace remaining button
      parent_element.childNodes[2].disabled = true;
      // Replacing the class by path-selected
      $(parent_element).removeClass("path-not-selected");
      $(parent_element).addClass("path-selected");
    }

    document.getElementById("files_count").innerHTML =
      "<b>Remaining files to make skip/replace selection: </b>" + 0;
  };

  // Replace Button
  document.querySelectorAll(".replace-button").forEach(function (el) {
    el.addEventListener("click", function () {
      SkipAllBtn.innerHTML = "Skip Remaining";
      ReplaceAllBtn.innerHTML = "Replace Remaining";

      // disable the button after a click
      el.disabled = true;

      replace_id = $(this).parent()[0].id;
      replace_parent_element = $(this).parent();

      file_path = $(this).prev().prev()[0].innerText;

      skip_button = $(this).prev()[0];

      // Storing the ids of path in dictionary with respect to specific action
      skip_replace_id_dict[parseInt(replace_id)] = "replace";
      // e.g. - skip_replace_id_dict = {0: replace}

      // Replacing the class by 'path-selected' after clicking on replace button

      replaceClass(replace_parent_element);

      // if the user clicks first on skip button, and then clicks on replace button, skip button should get enabled
      if (skip_button.disabled == true) {
        skip_button.disabled = false;

        // Remove the path from skip path array after clicking on replace button
        var path_index = skip_path_array.indexOf(file_path);
        skip_path_array.splice(path_index, 1);
      }

      not_selected_paths = document.querySelectorAll(".path-not-selected");
      document.getElementById("files_count").innerHTML =
        "<b>Remaining files to make skip/replace selection: </b>" +
        not_selected_paths.length;
    });
  });

  // Skip Button
  skip_list = [];
  document.querySelectorAll(".skip-button").forEach(function (el) {
    el.addEventListener("click", function () {
      SkipAllBtn.innerHTML = "Skip Remaining";
      ReplaceAllBtn.innerHTML = "Replace Remaining";

      el.disabled = true;

      skip_id = $(this).parent()[0].id;

      skip_parent_element = $(this).parent();

      file_path = $(this).prev()[0].innerText;

      replace_button = $(this).next()[0];

      // Storing the ids of path in dictionary with respect to specific action
      skip_replace_id_dict[parseInt(skip_id)] = "skip";
      // e.g. - skip_replace_id_dict = {0: skip}

      // Replacing the class by 'path-selected' after clicking on skip button
      replaceClass(skip_parent_element);

      // if the user clicks first on replace button, and then clicks on skip button, replace button should get enabled
      if (replace_button.disabled == true) {
        replace_button.disabled = false;
      }

      skip_path_array.push(file_path);

      not_selected_paths = document.querySelectorAll(".path-not-selected");

      document.getElementById("files_count").innerHTML =
        "<b>Remaining files to make skip/replace selection: </b>" +
        not_selected_paths.length;
    });
  });

  // When the user clicks anywhere outside the window, close it
  window.onclick = function (event) {
    if (event.target == warning_modal) {
      warning_modal.style.display = "none";
      btn = document.getElementById("flowPost");
      btn.innerHTML = "Upload";
      btn.disabled = false;
      document.getElementById("progress_bar_flow").style.display = "none";
      // Empty skip files array to undo skip actions
      skip_path_array = [];
    }
  };
}

function start(response) {
  let res = JSON.parse(response);
  flow.opts.query.depositId = res.deposit_id;
  currentDepositId = flow.opts.query.depositId;

  flow.upload();
}

function registerDeposit(remaining_files) {
  btn = document.getElementById("flowPost");
  btn.innerHTML = "Uploading...";
  btn.disabled = true;

  //Showing progress bar
  document.getElementById("progress_bar_flow").style.display = "inline-block";

  let coll_input = document.getElementById("id_collection");
  let collection_id = coll_input?.options[coll_input.selectedIndex].value;

  let xhr = new XMLHttpRequest();
  xhr.onreadystatechange = function () {
    if (xhr.readyState === 4) {
      start(xhr.response);
    }
  };

  xhr.open("POST", URLS.api_register_deposit, true);
  xhr.setRequestHeader("Content-Type", "application/json");
  let payload = {
    collection_id: collection_id,
    files: remaining_files,
    total_size: upload_size,
    parent_node_id: PARENT_NODE_ID || null,
  };
  xhr.send(JSON.stringify(payload));
  xhr.onloadend = function () {
    if (xhr.status == 200) {
      response = JSON.parse(xhr.response);
      let deposit_id = response["deposit_id"];
    }
  };
}

const createQuotaDonut = () => {
  let data = [];
  data.push(
    (
      parseInt(document.querySelector("#total_used_quota").value) /
      1024 ** 3
    ).toFixed(5)
  );
  data.push(
    (
      parseInt(
        document.querySelector("#organization_quota").value -
          document.querySelector("#total_used_quota").value
      ) /
      1024 ** 3
    ).toFixed(5)
  );
  createCollectionsChart(["Used", "Available"], data);
};

const createCollectionsChart = (collections, fileCounts) => {
  $("#collections-chart .chart-container").remove();
  chartalign.register(
    "#collections-chart",
    function () {
      return $("<canvas></canvas>")
        .attr("width", "50px")
        .attr("height", "45px");
    },
    function ($el) {
      return new Chart($el.get(0), {
        type: "doughnut",
        data: {
          labels: collections,
          datasets: [
            {
              label: "Collections",
              backgroundColor: [
                "#3e95cd",
                "#8e5ea2",
                "#306ccd",
                "#a27698",
                "#21ba60",
                "#e8e6c5",
                "#c45850",
                "#3cba9f",
                "#e8c3b9",
                "#c45850",
              ],
              data: fileCounts,
            },
          ],
        },
        options: {
          legend: { display: false },
          title: {
            display: true,
            text: "Quota (in GiB)",
          },
        },
      });
    },
    function (chart) {
      chart.destroy();
    }
  );
};

const resetForm = () => {
  const newLocation = window.location.href.split("?")[0];
  window.location = newLocation;
};

$(() => {
  $("#collections-chart .spinner").hide();
  $("label[for='id_collection']").html(
    "Collections:  <a href='javascript:void(0);' onclick='show_modal();'>Create a new Collection</a>"
  );
  createQuotaDonut();
});
