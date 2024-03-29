/* global $, ChunkedFileReader, SparkMD5, createCollectionsChart */

window.onload = function () {
  if (!document.querySelector("#id_dir_field")) {
    return;
  }

  let globalStartTime = performance.now();
  const retryDelay408 = 60000; // 1 minute
  const retryTimeout408 = (retryDelay408 / 1000) * 20; // 20 minutes
  let retryTimeoutID408 = {};
  let ABORT_REQUESTED = false;
  let RETRYING_ON_408 = false;

  document.querySelector("#cancel_button").value = "Reset Form";
  document.querySelector("#cancel_button").addEventListener("click", resetForm);

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

  createQuotaDonut();

  function enforceQuota(totalUploadSize, files) {
    const quota = parseInt(document.querySelector("#organization_quota").value);
    const usedQuota = parseInt(
      document.querySelector("#total_used_quota").value
    );

    document.querySelector("#stats").innerHTML = "";

    if (usedQuota + totalUploadSize > quota) {
      document.querySelector("#id_directories").value = "";
      document.querySelector("#id_sizes").value = "";
      document.querySelector("#id_file_field").disabled = false;
      document.querySelector("#id_dir_field").disabled = false;
      document.querySelector("#id_file_field").value = "";
      document.querySelector("#id_dir_field").value = "";

      let msg = "Your upload of size " + formatBytes(totalUploadSize, 3);
      msg += " will take you over your Quota of " + formatBytes(quota, 3);
      msg += ". Total used quota: " + formatBytes(usedQuota, 3);
      alert(msg);
    } else {
      doSomeSums(files);
    }
  }

  document
    .querySelector("#id_dir_field")
    .addEventListener("change", function () {
      document.querySelector("#id_file_field").disabled = true;
      globalStartTime = performance.now();
      const directories = [];
      const sizes = [];
      const files = document.querySelector("#id_dir_field").files;

      for (const file of files) {
        directories.push(file.webkitRelativePath);
        sizes.push(file.size);
      }

      document.querySelector("#id_directories").value = directories.toString();
      document.querySelector("#id_sizes").value = sizes.toString();

      enforceQuota(
        sizes.reduce((a, b) => a + b, 0),
        files
      );
    });

  document
    .querySelector("#id_file_field")
    .addEventListener("change", function () {
      document.querySelector("#id_dir_field").disabled = true;
      globalStartTime = performance.now();
      const directories = [];
      const sizes = [];
      const files = document.querySelector("#id_file_field").files;

      for (const file of files) {
        directories.push(file.name);
        sizes.push(file.size);
      }

      document.querySelector("#id_directories").value = directories.toString();
      document.querySelector("#id_sizes").value = sizes.toString();

      enforceQuota(
        sizes.reduce((a, b) => a + b, 0),
        files
      );
    });

  // We're uploading, we don't want to lose our window/tab on an idle click!
  function setAllTargets(T) {
    document.querySelectorAll("a").forEach(function (node) {
      node.setAttribute("target", T);
    });
  }

  let promises = [];
  let shasumsList = [];
  const form = document.querySelector("form");

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    document.querySelector("#Submit").disabled = true;

    // Empty message box
    document.querySelector("#stats").innerHTML = "";

    // Checking if either the file/directory is selected for upload
    if (document.querySelector("#id_directories").value) {
      // Showing progress bar
      document.getElementById("progress_bar").style.display = "inline-block";
      // Changing the text of upload button
      $("#Submit").val("Uploading...");

      // Checking to see if all shasums have been calculated before posting to server.
      Promise.allSettled(promises).then(() => {
        // Just a safety layer so that doSomeSums function's .then() gets executed before.
        setTimeout(function () {
          XHRuploadFiles(form);
        }, 100);
      });
    } else {
      // Showing message to select a file/directory before clicking submit button
      document.querySelector("#stats").innerHTML =
        "<b>Please select files/directories to upload.</b>";
      document.querySelector("#Submit").disabled = false;
    }
  });

  async function XHRuploadFiles(form) {
    let totalSize = 0;
    let numFiles = 0;
    let files = [];

    setAllTargets("_blank");

    if (RETRYING_ON_408 === false) {
      ABORT_REQUESTED = false;
    }
    let start = performance.now();

    if (document.querySelector("#id_file_field").disabled === true) {
      files = document.querySelector("#id_dir_field").files;
    } else {
      files = document.querySelector("#id_file_field").files;
    }

    const data = new FormData(form);

    for (const f of files) {
      totalSize = totalSize + f.size;
      numFiles = numFiles + 1;
      data.append("file", f);
    }

    const xhr = new XMLHttpRequest();

    function abortXHR() {
      if (xhr) {
        document.querySelector("#cancel_button").disabled = true;
        document.querySelector("#cancel_button").value = "Cancelling Job...";
        ABORT_REQUESTED = 1;
        if (RETRYING_ON_408) {
          RETRYING_ON_408 = false;
          clearTimeout(retryTimeoutID408);
          XHRuploadFiles(form);
        } else {
          xhr.abort();
        }
      } else {
        resetForm();
      }

      return false;
    }

    // We might be looping on a retry
    document.querySelector("#cancel_button").value = "Cancel Upload";
    document
      .querySelector("#cancel_button")
      .removeEventListener("click", resetForm);
    document
      .querySelector("#cancel_button")
      .removeEventListener("click", abortXHR);
    document
      .querySelector("#cancel_button")
      .addEventListener("click", abortXHR);

    xhr.open("POST", "/vault/deposit/web", true);

    xhr.onerror = function () {
      const msg = "Request FAILED - Network Error.";
      console.error(msg);
      document.querySelector("#stats").innerHTML = "<b>" + msg + "</b>";
    };

    xhr.onabort = function () {
      const msg = "Upload Cancelled";
      console.info(msg);
      document.querySelector("#stats").innerHTML = "<b>" + msg + "</b>";
      setTimeout(function () {
        document.querySelector("#stats").innerHTML = "";
      }, 4000);
      ABORT_REQUESTED = 1;
    };

    xhr.upload.onprogress = function (e) {
      if (e.lengthComputable) {
        const progress = Math.round((e.loaded / e.total) * 100);
        document.querySelector("#progress_bar").value = progress;
      }
    };

    xhr.onloadend = function () {
      let msg = "";
      let res = {};
      let reportId = "";
      const end = performance.now();
      const delay = retryDelay408 / 1000;
      const runtime = ((end - start) / 1000).toFixed(2);
      const ttime = ((end - globalStartTime) / 1000).toFixed(2);

      if (xhr.status === 200) {
        start = end;

        try {
          res = JSON.parse(xhr.response);
          reportId = res[res.length - 2]["report_id"];
        } catch (err) {
          if (xhr.response.length === 0) {
            res = "No Data.";
          } else {
            res = xhr.response;
          }
          console.error("JSON parse error: " + err + "Data: " + res);
          reportId = "undefined";
        }

        try {
          const totalUsedQuota = res[res.length - 1]["total_used_quota"];
          document.querySelector("#total_used_quota").value = totalUsedQuota;
        } catch (err) {
          if (xhr.response.length === 0) {
            res = "No Data.";
          } else {
            res = xhr.response;
          }
          console.error("JSON parse error: " + err + "Data: " + res);
        }

        msg += " Files transfered: " + numFiles + ",";
        msg += " Size: " + formatBytes(totalSize);
        msg += " and Runtime: " + runtime + "s";
        msg +=
          '<a href="/vault/reports/' +
          String(reportId) +
          '" target="_blank"> View Report </a>';
        document.querySelector("#stats").innerHTML = "<b>" + msg + "</b>";

        createQuotaDonut();
      } else if (xhr.status < 400) {
        start = end;
        if (xhr.response.length > 0) {
          msg += "Status: " + xhr.status + ": " + xhr.response;
        } else {
          msg += "Status: " + xhr.status;
        }
      } else if (xhr.status === 408 && ABORT_REQUESTED === false) {
        if (ttime < retryTimeout408) {
          RETRYING_ON_408 = true;
          msg += "Upload Timed Out in " + runtime;
          msg += "s: Retrying in " + delay + "s.";
          msg += "Total Elapsed Time: " + ttime + "s";
          document.querySelector("#stats").innerHTML = "<b>" + msg + "</b>";
        } else {
          msg += "Maximum Timeout Retries Reached, Try Again Later!";
          document.querySelector("#stats").innerHTML +=
            "<br><b>" + msg + "</b>";
        }
      } else if (ABORT_REQUESTED === false) {
        start = end;
        msg +=
          "Status: " +
          xhr.status +
          ": " +
          xhr.response +
          " After " +
          runtime +
          "s";
        document.querySelector("#stats").innerHTML += "<br><b>" + msg + "</b>";
      }

      if (msg.length > 0) {
        console.log(msg);
      }

      if (xhr.response.length > 0) {
        console.log(xhr.status + ": " + xhr.response);
      }

      if (
        xhr.status === 408 &&
        ttime < retryTimeout408 &&
        ABORT_REQUESTED === false
      ) {
        retryTimeoutID408 = setTimeout(function () {
          XHRuploadFiles(form);
        }, retryDelay408);
      } else {
        document
          .querySelector("#cancel_button")
          .removeEventListener("click", abortXHR);
        resetForm();
      }
    };

    xhr.send(data);
  }

  function resetForm() {
    setAllTargets("_top");
    document.querySelector("#upload_form").reset();
    document.querySelector("#progress_bar").style.display = "none";
    document.querySelector("#Submit").value = "Upload Files";
    document.querySelector("#id_directories").value = "";
    document.querySelector("#id_sizes").value = "";
    document.querySelector("#Submit").disabled = false;
    document.querySelector("#id_file_field").disabled = false;
    document.querySelector("#id_dir_field").disabled = false;
    document.querySelector("#cancel_button").disabled = false;
    document.querySelector("#progress_bar").value = 0;
    document.querySelector("#cancel_button").value = "Reset Form";
    document
      .querySelector("#cancel_button")
      .removeEventListener("click", resetForm);
    document
      .querySelector("#cancel_button")
      .addEventListener("click", resetForm);
    console.log("Form reset!");
    if (ABORT_REQUESTED) {
      document.querySelector("#stats").innerHTML = "<b>Upload Cancelled!</b>";
      ABORT_REQUESTED = false;
    }
    return false;
  }

  function bytesToHexString(bytes) {
    if (!bytes) {
      return null;
    }
    bytes = new Uint8Array(bytes);
    const hexBytes = [];
    for (let i = 0; i < bytes.length; ++i) {
      let byteString = bytes[i].toString(16);
      if (byteString.length < 2) {
        byteString = "0" + byteString;
      }
      hexBytes.push(byteString);
    }
    return hexBytes.join("");
  }

  // eslint-disable-next-line no-unused-vars
  async function sha256HashFile(file, idx) {
    const buffer = await file.arrayBuffer();
    return crypto.subtle.digest("SHA-256", buffer).then(function (hash) {
      shasumsList[idx] = bytesToHexString(hash);
    });
  }

  async function doSomeSums(files) {
    const tooBig = 1024 * 1024 * 1024; // 1GiB
    promises = []; // GLOBAL
    let idx = 0;
    shasumsList = [];
    for (const file of files) {
      if (ABORT_REQUESTED) {
        continue;
      }
      if (file.size < tooBig) {
        shasumsList[idx] =
          "0000000000000000000000000000000000000000000000000000000000000000";
        // promises.push(sha256HashFile(file, idx));
      } else {
        shasumsList[idx] =
          "0000000000000000000000000000000000000000000000000000000000000000";
        // document.querySelector('#stats').innerHTML = 'Calculating MD5sum of ' + formatBytes(file.size) + ' file ' + file.name;
        // await MD5HashFile(file, idx).then((data) => {
        //          shasumsList[idx] = data;
        //       });
        // document.querySelector('#stats').innerHTML = 'Done calculating MD5sums!';
      }
      idx++;
    }
    Promise.allSettled(promises).then(() => {
      document.querySelector("#id_shasums").value = shasumsList.toString();
    });
  }

  // eslint-disable-next-line no-unused-vars
  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  // eslint-disable-next-line no-unused-vars
  async function MD5HashFile(file, _idx) {
    return new Promise((resolve, _reject) => {
      const spark = new SparkMD5.ArrayBuffer();
      const reader = new ChunkedFileReader();

      reader.subscribe("chunk", function (e) {
        spark.append(e.chunk);
      });

      reader.subscribe("end", function (_e) {
        const hash = spark.end();
        resolve(hash);
      });

      reader.readChunks(file);
    });
  }

  // END of window.onload()
};
