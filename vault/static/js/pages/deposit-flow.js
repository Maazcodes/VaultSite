/* global URLS, Flow, md5, $, Chart, chartalign, PARENT_NODE_ID */

function secondsToString(seconds) {
  const remainingMin = Math.floor(seconds / 60);
  const remainingSec = seconds - remainingMin * 60;

  // For hours
  const remainingHours = Math.floor(seconds / 3600);
  const totalRemainingSecHr = seconds - remainingHours * 3600; // Total remaining seconds after hours
  const remainingSecondsAfterMin = Math.floor(totalRemainingSecHr / 60); // Converting remaining seconds into minutes to get remaining minutes
  const actualRemainingSecs = seconds - remainingSecondsAfterMin * 60; // Getting remaining seconds after minutes

  if (seconds <= 60) {
    return seconds + " s ";
  } else if (seconds > 60 && seconds <= 3600) {
    return remainingMin + " m " + remainingSec + " s ";
  } else if (seconds > 3600) {
    return (
      remainingHours +
      " h " +
      remainingSecondsAfterMin +
      " m " +
      actualRemainingSecs +
      " s "
    );
  }
}

const formatBytes = (bytes, decimals = 2) => {
  if (bytes === 0) {
    return "0 Bytes";
  }

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

const flow = new Flow({
  target: URLS.api_flow_chunk,
  // eslint-disable-next-line camelcase
  query: { upload_token: "my_token" },
  simultaneousUploads: 3,
  speedSmoothingFactor: 0.005,
  progressCallbacksInterval: 1000,
  maxChunkRetries: undefined,
  permanentErrors: [],
  chunkRetryInterval: 5000,
  allowDuplicateUploads: true,
  generateUniqueIdentifier: function (file) {
    const relativePath =
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
let uploadSize = 0;
let currentDepositId = undefined;
const filesDict = {};
const flowfileObjectsDict = {};

flow.on("fileAdded", function (file, _event) {
  const newFile = {
    // eslint-disable-next-line camelcase
    flow_identifier: file.uniqueIdentifier,
    name: file.name,
    // eslint-disable-next-line camelcase
    relative_path: file.relativePath,
    size: file.size,
    type: file.file.type,
    // eslint-disable-next-line camelcase
    pre_deposit_modified_at: new Date(file.file.lastModified).toISOString(),
  };
  files.push(newFile);
  flowfileObjectsDict[String(file["relativePath"])] = file;
  // dictionary with relative path as key
  filesDict[String(newFile["relative_path"])] = newFile;
  uploadSize += newFile["size"];
  document.querySelector("#dropTargetMsg").innerHTML =
    "<div>" +
    files.length +
    pluralizeWord(" file ", " files ", files.length) +
    " selected. Total Upload Size: " +
    formatBytes(uploadSize) +
    "</div>";
});

flow.on("fileSuccess", function (_file, _message) {});

function pluralizeWord(singularWord, pluralWord, count) {
  return count !== 1 ? pluralWord : singularWord;
}

flow.on("fileError", function (file, message) {
  console.log(file, message);
  const btn = document.getElementById("flowPost");
  btn.innerHTML = "Upload";
  btn.disabled = false;
  document.querySelector("#flow-stats").innerHTML = "Error Uploading";
});

function changeStats() {
  if ($("#id_collection").find(":selected").val() !== "") {
    document.querySelector("#dropTargetMsg").innerHTML =
      "<div>" +
      files.length +
      pluralizeWord(" file ", " files ", files.length) +
      " selected. Total Upload Size: " +
      formatBytes(uploadSize) +
      "</div>";
  }
}

document
  .getElementById("id_collection")
  ?.addEventListener("change", changeStats);

// eslint-disable-next-line camelcase
function deposit_status(time) {
  if (!currentDepositId) {
    console.error("Deposit Id not defined");
  }
  const xhr = new XMLHttpRequest();
  xhr.open("GET", `${URLS.api_deposit_status}?deposit_id=${currentDepositId}`);
  xhr.setRequestHeader("Content-Type", "application/json");
  xhr.send();
  xhr.onloadend = function () {
    if (xhr.status === 200) {
      const res = JSON.parse(xhr.response);
      const processing =
        res["hashed_files"] + res["replicated_files"] + res["errored_files"];
      const message =
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
    } else if (xhr.status === 400) {
      console.error("Deposit Error: No Deposit ID");
      document.querySelector("#flow-stats").innerHTML =
        "Deposit Error: No Deposit ID";
    } else if (xhr.status === 404) {
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
  warnOnNavigation(false);
  document.querySelector("#flow-stats").innerHTML = "Upload Complete";
  const btn = document.getElementById("flowPost");
  btn.innerHTML = "Upload";
  btn.disabled = false;
  files = [];
  uploadSize = 0;
  document.querySelector("#progress_bar_flow").style.display = "none";
  deposit_status(0);
});

let initialTime = 0;
let sumSpeed = 0;
let counter = 0;
flow.on("progress", function () {
  if (counter === 0) {
    initialTime = Date.now();
    counter++;
    return;
  }
  counter++;
  const uploadedSize = flow.sizeUploaded();
  const passedTime = Date.now() - initialTime;
  const speed = uploadedSize / passedTime;
  sumSpeed += speed;
  const avgSpeed = sumSpeed / counter;
  const totalFileSize = flow.getSize();
  const timeRemaining = (totalFileSize - uploadedSize) / avgSpeed;
  document.querySelector("#flow-stats").innerHTML =
    "Uploading Files (" +
    " Time left: " +
    secondsToString(Math.floor(timeRemaining / 1000)) +
    ") ";
  document.querySelector("#progress_bar_flow").value = flow.progress() * 100;
});

const warningheader = document.getElementById("warningHeader");

// eslint-disable-next-line no-unused-vars, camelcase
function start_deposit(flow, files) {
  if ($("#id_collection").find(":selected").val() === "") {
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
  const collInput = document.getElementById("id_collection");
  const collectionId = collInput?.options[collInput.selectedIndex].value;

  const btn = document.getElementById("flowPost");
  btn.innerHTML = "Uploading...";
  btn.disabled = true;

  const xhr = new XMLHttpRequest();

  xhr.open("POST", URLS.api_warning_deposit, true);
  xhr.setRequestHeader("Content-Type", "application/json");
  const payload = {
    // eslint-disable-next-line camelcase
    collection_id: collectionId,
    files: files,
    // eslint-disable-next-line camelcase
    total_size: uploadSize,
    // eslint-disable-next-line camelcase
    parent_node_id: PARENT_NODE_ID || null,
  };
  xhr.send(JSON.stringify(payload));
  xhr.onloadend = function () {
    if (xhr.status === 200) {
      const response = JSON.parse(xhr.response);
      const objectsList = response["objects"]; // All matched files
      const pathList = response["relative_path"];
      const filesList = [];
      const paths = [];
      for (let index = 0; index < objectsList.length; index++) {
        const element = objectsList[index];
        const fileName = element["name"];
        filesList.push(fileName);
      }

      for (let index = 0; index < pathList.length; index++) {
        const pathElement = pathList[index];
        paths.push(pathElement);
      }

      if (filesList.length > 0) {
        warnOnNavigation(false);
        overlappedFiles(filesList, false);
      } else if (paths.length > 0) {
        warnOnNavigation(false);
        overlappedFiles(paths, false);
      } else {
        warnOnNavigation(true);
        registerDeposit(files);
      }

      // reversing all the actions after clicking outside the window and again on upload button
      const SkipreplaceBtns = $(".skipreplace");
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

function replaceClass(skipOrReplaceElement) {
  if (skipOrReplaceElement.hasClass("path-not-selected")) {
    skipOrReplaceElement.removeClass("path-not-selected");
    skipOrReplaceElement.addClass("path-selected");
  }
}

let skipPathArray = [];

const skipReplaceIdDict = {};

// Start of warning function

function overlappedFiles(overlappedFilesList, confirmButtonStatus) {
  // Get the modal
  const warningModal = document.getElementById("warningModal_id");

  // When the user clicks on the button, open the modal
  warningModal.style.display = "block";

  // Skip All and Replace All Buttons
  warningheader.innerHTML =
    "<br>" +
    '<button class="button small skipBtn" id="skipall" style = "margin-right: 10px; margin-left: 10px; border-radius: 20px; padding: 10px 20px 10px 20px;"> Skip All </button><button class="button small replaceBtn" id="replaceall" style = "border-radius: 20px; padding: 10px 20px 10px 20px;"> Replace All</button>' +
    `<div id = "files_count" style = "font-style: italic; margin-bottom: 20px;"><b>Remaining files to make skip/replace selection: </b>${overlappedFilesList.length} </div>`;

  // Adding Confirm button before all rows
  warningheader.innerHTML += `<br><button class="confirm-button"> Confirm </button><div id="confirmBtn1text"></div><br><br>`;

  for (let index = 0; index < overlappedFilesList.length; index++) {
    const fileElement = overlappedFilesList[index];

    // Adding Skip and Replace buttons after every matched path
    warningheader.innerHTML +=
      '<div class="path-not-selected" id="' +
      String(index) +
      '" style = " margin-bottom: 0px; display: flex; box-sizing: border-box; flex-wrap: wrap; height: 32px; vertical-align: middle;">' +
      '<div style="margin-top: 7px; height: 42px; display:inline-block; box-sizing: border-box; flex: 60%; max-width: 500px; left: 0px; text-align: left; vertical-align: middle;" id = "text" >' +
      fileElement +
      "</div>" +
      '<button class="button small skip-button skipreplace skipBtn " style = "border-radius: 20px; right: -190px; height: 36px; padding: 7px 15px 7px 15px; position: relative;"> Skip </button><button class="button small replace-button skipreplace replaceBtn " style = "border-radius: 20px; height: 36px; right: -200px; padding: 7px 15px 7px 15px; margin-right: 0px;"> Replace </button></div><hr>';
  }

  // Adding another Confirm button after all rows
  warningheader.innerHTML += `<br><button class="confirm-button"> Confirm </button>`;

  if (confirmButtonStatus) {
    // displaying the message if no action is performed on all the paths
    document.getElementById("confirmBtn1text").innerHTML =
      "<b>Please select skip or replace on all files</b>";
    warningheader.innerHTML +=
      "<div><b>Please select skip or replace on all files</b></div>";

    // Changing the text after clicking on confirm button
    document.getElementById("skipall").innerHTML = "Skip Remaining";
    document.getElementById("replaceall").innerHTML = "Replace Remaining";

    // maintaining all the previous actions after clicking on confirm button
    for (const key in skipReplaceIdDict) {
      // here key is id and value is skip or replace
      // getting skip and replace elements from the same id
      const skipElement = $("#" + key)[0].childNodes[1];
      const replaceElement = $("#" + key)[0].childNodes[2];

      const value = skipReplaceIdDict[key];
      if (value === "skip") {
        skipElement.disabled = true;
      } else {
        replaceElement.disabled = true;
      }

      // removing this class to remove the element from path-not-selected list
      $("#" + key).removeClass("path-not-selected");
    }

    const notSelectedPaths = document.querySelectorAll(".path-not-selected");
    document.getElementById("files_count").innerHTML =
      "<b>Remaining files to make skip/replace selection: </b>" +
      notSelectedPaths.length;
  }

  // collecting both the confirm buttons to add event listeners
  const confirmButtons = document.querySelectorAll(".confirm-button");
  confirmButtons.forEach(function (button) {
    button.addEventListener("click", function () {
      const notSelectedPaths = document.querySelectorAll(".path-not-selected");
      // if no action is performed on all paths, repeat the same function with previous changes
      if (notSelectedPaths.length > 0) {
        // setting confirm button status as true after the user clicks on confirm button
        overlappedFiles(overlappedFilesList, true);
      } else {
        warningModal.style.display = "none";

        for (let index = 0; index < skipPathArray.length; index++) {
          const path = skipPathArray[index];
          // Removing the skipped file from upload queue by relative path
          flow.removeFile(flowfileObjectsDict[path]);

          // Deleting elements from dictionary by relative path
          delete filesDict[path];
        }

        const finalDepositList = Object.values(filesDict);
        registerDeposit(finalDepositList);
      }
    });
  });

  // Skip All Button
  const SkipAllBtn = document.getElementById("skipall");
  const ReplaceAllBtn = document.getElementById("replaceall");
  SkipAllBtn.onclick = function () {
    SkipAllBtn.style.backgroundColor = "darkgreen";
    const notSelectedElements = $(".path-not-selected");
    for (let index = 0; index < notSelectedElements.length; index++) {
      const parentElement = notSelectedElements[index];
      const filePath = parentElement.childNodes[0].innerText;
      // appending skip path array with the file path
      skipPathArray.push(filePath);
      // Disable all not selected skip buttons after clicking on Skip All/Skip remaining button
      parentElement.childNodes[1].disabled = true;
      // Replacing the class by path-selected
      $(parentElement).removeClass("path-not-selected");
      $(parentElement).addClass("path-selected");
    }

    document.getElementById("files_count").innerHTML =
      "<b>Remaining files to make skip/replace selection: </b>" + 0;
  };

  // Replace All Button
  ReplaceAllBtn.onclick = function () {
    ReplaceAllBtn.style.backgroundColor = "red";
    // Disable all replace buttons after clicking on Replace All button
    const notSelectedElements = $(".path-not-selected");
    for (let index = 0; index < notSelectedElements.length; index++) {
      const parentElement = notSelectedElements[index];
      // Disable all not selected replace buttons after clicking on Replace All/Replace remaining button
      parentElement.childNodes[2].disabled = true;
      // Replacing the class by path-selected
      $(parentElement).removeClass("path-not-selected");
      $(parentElement).addClass("path-selected");
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

      const replaceId = $(this).parent()[0].id;
      const replaceParentElement = $(this).parent();
      const filePath = $(this).prev().prev()[0].innerText;
      const skipButton = $(this).prev()[0];

      // Storing the ids of path in dictionary with respect to specific action
      skipReplaceIdDict[parseInt(replaceId)] = "replace";
      // e.g. - skip_replace_id_dict = {0: replace}

      // Replacing the class by 'path-selected' after clicking on replace button

      replaceClass(replaceParentElement);

      // if the user clicks first on skip button, and then clicks on replace button, skip button should get enabled
      if (skipButton.disabled === true) {
        skipButton.disabled = false;

        // Remove the path from skip path array after clicking on replace button
        const pathIndex = skipPathArray.indexOf(filePath);
        skipPathArray.splice(pathIndex, 1);
      }

      const notSelectedPaths = document.querySelectorAll(".path-not-selected");
      document.getElementById("files_count").innerHTML =
        "<b>Remaining files to make skip/replace selection: </b>" +
        notSelectedPaths.length;
    });
  });

  // Skip Button
  document.querySelectorAll(".skip-button").forEach(function (el) {
    el.addEventListener("click", function () {
      SkipAllBtn.innerHTML = "Skip Remaining";
      ReplaceAllBtn.innerHTML = "Replace Remaining";

      el.disabled = true;

      const skipId = $(this).parent()[0].id;
      const skipParentElement = $(this).parent();
      const filePath = $(this).prev()[0].innerText;
      const replaceButton = $(this).next()[0];

      // Storing the ids of path in dictionary with respect to specific action
      skipReplaceIdDict[parseInt(skipId)] = "skip";
      // e.g. - skip_replace_id_dict = {0: skip}

      // Replacing the class by 'path-selected' after clicking on skip button
      replaceClass(skipParentElement);

      // if the user clicks first on replace button, and then clicks on skip button, replace button should get enabled
      if (replaceButton.disabled === true) {
        replaceButton.disabled = false;
      }

      skipPathArray.push(filePath);

      const notSelectedPaths = document.querySelectorAll(".path-not-selected");

      document.getElementById("files_count").innerHTML =
        "<b>Remaining files to make skip/replace selection: </b>" +
        notSelectedPaths.length;
    });
  });

  // When the user clicks anywhere outside the window, close it
  window.onclick = function (event) {
    if (event.target === warningModal) {
      warningModal.style.display = "none";
      const btn = document.getElementById("flowPost");
      btn.innerHTML = "Upload";
      btn.disabled = false;
      document.getElementById("progress_bar_flow").style.display = "none";
      // Empty skip files array to undo skip actions
      skipPathArray = [];
    }
  };
}

function start(response) {
  const res = JSON.parse(response);
  flow.opts.query.depositId = res.deposit_id;
  currentDepositId = flow.opts.query.depositId;

  flow.upload();
}

function registerDeposit(remainingFiles) {
  const btn = document.getElementById("flowPost");
  btn.innerHTML = "Uploading...";
  btn.disabled = true;

  // Showing progress bar
  document.getElementById("progress_bar_flow").style.display = "inline-block";

  const collInput = document.getElementById("id_collection");
  const collectionId = collInput?.options[collInput.selectedIndex].value;

  const xhr = new XMLHttpRequest();
  xhr.onreadystatechange = function () {
    if (xhr.readyState === 4) {
      start(xhr.response);
    }
  };

  xhr.open("POST", URLS.api_register_deposit, true);
  xhr.setRequestHeader("Content-Type", "application/json");
  const payload = {
    // eslint-disable-next-line camelcase
    collection_id: collectionId,
    files: remainingFiles,
    // eslint-disable-next-line camelcase
    total_size: uploadSize,
    // eslint-disable-next-line camelcase
    parent_node_id: PARENT_NODE_ID || null,
  };
  xhr.send(JSON.stringify(payload));
}

const createQuotaDonut = () => {
  const data = [];
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

// eslint-disable-next-line no-unused-vars
const resetForm = () => {
  const newLocation = window.location.href.split("?")[0];
  window.location = newLocation;
};

const handleBeforeUnload = (e) => {
  // see: https://developer.mozilla.org/en-US/docs/Web/API/WindowEventHandlers/onbeforeunload#examples
  e.preventDefault();
  return "";
};

const warnOnNavigation = (doWarn) => {
  if (doWarn) {
    window.addEventListener("beforeunload", handleBeforeUnload);
  } else {
    window.removeEventListener("beforeunload", handleBeforeUnload);
  }
};

$(() => {
  $("#collections-chart .spinner").hide();
  $("label[for='id_collection']").html(
    "Collections:  <a href='javascript:void(0);' onclick='show_modal();'>Create a new Collection</a>"
  );
  createQuotaDonut();
});
