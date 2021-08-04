window.onload = function () {
    if ( ! document.querySelector('#id_dir_field') ) { return }
    globalStartTime = performance.now();
    globalRetryDelay = 60000; //1 minute
    globalRetryTimeout = globalRetryDelay / 1000 * 20; //20 minutes
    ABORT_REQUESTED = false;

    document.querySelector("#cancel_button").value = "Reset Form";
    document.querySelector('#cancel_button').addEventListener("click", resetForm);

    function getTotalUsedData() {
        let xhr = new XMLHttpRequest();
        xhr.open('POST', '/vault/api/collections_stats', false);
        xhr.send();

        if (xhr.status === 200) {
            let res           = JSON.parse(xhr.responseText);
            let consumedBytes = 0;
            
            for (let collection of res.collections) {
                consumedBytes += (collection.totalSize || 0);
            }
            
            return consumedBytes;
        }
        else {
            // TODO: on error from API.
            console.error('<b>Request Failed: Failed to fetch collection stats.</b>');
        }
    }

    function enforceQuota(totalUploadSize, files) {
        let quota        = parseInt(document.querySelector("#organization_quota").value);
        let accountStats = getTotalUsedData();
        
        document.querySelector('#stats').innerHTML = '';

        if(accountStats + totalUploadSize > quota) {
            
            document.querySelector("#id_directories").value       = "";
            document.querySelector("#id_sizes").value             = "";
            document.querySelector("#id_file_field").disabled     = false;
            document.querySelector("#id_dir_field").disabled      = false;
            document.querySelector("#id_file_field").value        = "";
            document.querySelector("#id_dir_field").value         = "";
            
            alert("Your upload of size " + formatBytes(totalUploadSize, 3) + " will take you over your Quota of " + formatBytes(quota, 3) + ". Total used quota: " + formatBytes(accountStats, 3));
        }
        else {
            doSomeSums(files);
        }
    }

    document.querySelector("#id_dir_field").addEventListener("change", function() {
        document.querySelector("#id_file_field").disabled = true;
        globalStartTime = performance.now();
        let directories = [];
        let sizes       = [];
        let files = document.querySelector("#id_dir_field").files;
        for (var file of files) {
            directories.push(file.webkitRelativePath);
            sizes.push(file.size);
        }
        document.querySelector("#id_directories").value = directories.toString();
        document.querySelector("#id_sizes").value = sizes.toString();
        enforceQuota(sizes.reduce((a, b) => a + b, 0), files);
    });


    document.querySelector("#id_file_field").addEventListener("change", function() {
        document.querySelector("#id_dir_field").disabled = true;
        globalStartTime = performance.now();
        let directories = [];
        let sizes       = [];
        let files = document.querySelector("#id_file_field").files;
        for (var file of files) {
            directories.push(file.name);
            sizes.push(file.size);
        }
        document.querySelector("#id_directories").value = directories.toString();
        document.querySelector("#id_sizes").value = sizes.toString();
        enforceQuota(sizes.reduce((a, b) => a + b, 0), files);
    });

    let promises = [];
    let shasumsList = [];
    const form = document.querySelector('form');
    form.addEventListener('submit', event => {
        event.preventDefault();
        document.querySelector("#Submit").disabled = true;

        // Empty message box
        document.querySelector('#stats').innerHTML = '';

        // Checking if either the file/directory is selected for upload
        if (document.querySelector("#id_directories").value) {

            //Showing progress bar
            document.getElementById('progress_bar').style.display = 'inline-block';
            // Changing the text of upload button
            $('#Submit').val('Uploading...');

            // Checking to see if all shasums have been calculated before posting to server.
            Promise.allSettled(promises).then(() => {
                // Just a safety layer so that doSomeSums function's .then() gets executed before.
                setTimeout(function() { XHRuploadFiles(form); }, 100);
            });
        }
        else { // Showing message to select a file/directory before clicking submit button
            document.querySelector('#stats').innerHTML = 'Please select files/directories to upload.';
            document.querySelector("#Submit").disabled = false;
        }

    })

    function formatBytes(bytes, decimals = 2) {
        if (bytes === 0) return '0 Bytes';

        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];

        const i = Math.floor(Math.log(bytes) / Math.log(k));

        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    };

    async function XHRuploadFiles (form) {
        let total_size  = 0;
        let num_files   = 0;
        ABORT_REQUESTED = false;
        start = performance.now();

        let files = [];
        if (document.querySelector("#id_file_field").disabled == true) {
            files = document.querySelector("#id_dir_field").files;
        } else {
            files = document.querySelector("#id_file_field").files;
        };

        let data = new FormData(form);
        for (var f of files) {

            total_size = total_size + f.size;
            num_files  = num_files + 1;
            data.append('file', f);
         };

         let xhr = new XMLHttpRequest();
        
         function abortXHR() {
             if (xhr) {
                 xhr.abort();
             } else {
                 resetForm();
             }
             return false;
         };

         // We might be looping on a retry
         document.querySelector("#cancel_button").value = "Cancel Upload";
         document.querySelector('#cancel_button').removeEventListener("click", resetForm);
         document.querySelector('#cancel_button').removeEventListener("click", abortXHR);
         document.querySelector('#cancel_button').addEventListener("click", abortXHR);

         xhr.open('POST', '/vault/deposit/web', true);

         //xhr.responseType = 'json';
         //xhr.responseType = 'text';

         xhr.onerror = function () {
             let msg = 'Request FAILED - Network Error.';
             console.error(msg);
             document.querySelector('#stats').innerHTML = '<p>' + msg + '</p>';
         };

         xhr.onabort = function () {
             let msg = 'Request ABORTED!';
             console.info(msg);
             document.querySelector('#stats').innerHTML = '<p>' + msg + '</p>';
             setTimeout( function() { document.querySelector('#stats').innerHTML = "" }, 4000 );
             ABORT_REQUESTED = 1
         };

         xhr.upload.onprogress = function(e) {
             if (e.lengthComputable) {
                 let progress = Math.round((e.loaded / e.total)*100);
                 document.querySelector('#progress_bar').value = progress;
             };
         };

         xhr.onloadend = function() {
             let msg      = "";
             let res      = {};
             let report_id= '';
             let end      = performance.now();
             let delay    = globalRetryDelay / 1000;
             let runtime  = ((end - start) / 1000).toFixed(2);
             let ttime    = ((end - globalStartTime) / 1000).toFixed(2);
             if (xhr.status == 200) {
                start = end;

                try {
                    res = JSON.parse(xhr.response);
                    report_id = res[res.length - 1]["report_id"];
                }
                catch(err) {
                    console.error('JSON parse error: ' + err + 'Data: ' + xhr.response);
                    res = xhr.response;
                    report_id = 'undefined';
                }

                msg += ' Files transfered: ' + num_files + ',';
                msg += ' Size: ' + formatBytes(total_size);
                msg += ' and Runtime: ' + runtime + 's';
                msg += '<a href="/reports/'+ String(report_id) + '" target="_blank"> View Report </a>';
             } else if (xhr.status < 400) {
                start = end;
                msg += 'Status: ' + xhr.status + ': ' + xhr.response;
             } else if (xhr.status == 408) {
                 if (ttime < globalRetryTimeout) {
                    msg += 'Upload Timed Out in ' + runtime;
                    msg += 's: Retrying in ' + delay + 's.';
                    msg += 'Total Elapsed Time: ' + ttime + 's';
                 } else {
                    msg += 'Maximum Timeout Retries Reached, Try Again Later!';
                 }
             } else {
                start = end;
                msg += 'Status: ' + xhr.status + ': ' + xhr.response + ' After ' + runtime + 's';
             }

             document.querySelector('#stats').innerHTML += '<p>' + msg + '</p>'
             console.log(msg);
             if (xhr.response.length > 0) {
                console.log(xhr.status + ': ' + xhr.response);
             }

             if ((xhr.status == 408) && (ttime < globalRetryTimeout)) {
                setTimeout( function() { XHRuploadFiles(form); }, globalRetryDelay );
             } else {
                document.querySelector('#cancel_button').removeEventListener("click", abortXHR);
                resetForm();
             }
         };

         xhr.send(data);
    };


    function resetForm() {
        document.querySelector("#upload_form").reset();
        document.querySelector("#progress_bar").style.display = 'none';
        document.querySelector("#Submit").value               = "Upload Files";
        document.querySelector("#id_directories").value       = "";
        document.querySelector("#id_sizes").value             = "";
        document.querySelector("#Submit").disabled            = false;
        document.querySelector("#id_file_field").disabled     = false;
        document.querySelector("#id_dir_field").disabled      = false;
        document.querySelector('#progress_bar').value         = 0;
        document.querySelector("#cancel_button").value        = "Reset Form";
        document.querySelector('#cancel_button').removeEventListener("click", resetForm);
        document.querySelector('#cancel_button').addEventListener("click", resetForm);
        console.log("Form reset!");
        if ( ABORT_REQUESTED ) {
           document.querySelector('#stats').innerHTML = '<b>Uploading Aborted!</b>';
           ABORT_REQUESTED = false;
        }
        return false;
    };


    function bytesToHexString(bytes) {
        if (!bytes)
            return null;
        bytes = new Uint8Array(bytes);
        let hexBytes = [];
        for (let i = 0; i < bytes.length; ++i) {
            let byteString = bytes[i].toString(16);
            if (byteString.length < 2)
                byteString = "0" + byteString;
            hexBytes.push(byteString);
        };
        return hexBytes.join("");
    };


    async function sha256HashFile(file, idx) {
        let buffer = await file.arrayBuffer();
        return crypto.subtle.digest("SHA-256", buffer).then(function (hash) {
            shasumsList[idx] = bytesToHexString(hash);
        });
    };


    async function doSomeSums(files) {
        let tooBig = 1024*1024*1024; // 1GB
        promises = [];
        let idx = 0;
        shasumsList = [];
        for (var file of files) {
            if ( ABORT_REQUESTED ) {
                continue;
            }
            if (file.size < tooBig) {
                promises.push(sha256HashFile(file, idx));
            } else {
                shasumsList[idx] = '0000000000000000000000000000000000000000000000000000000000000000';
                //document.querySelector('#stats').innerHTML = 'Calculating MD5sum of ' + formatBytes(file.size) + ' file ' + file.name;
                await MD5HashFile(file, idx).then((data) => {
                    shasumsList[idx] = data;
                });
                //document.querySelector('#stats').innerHTML = 'Done calculating MD5sums!';
            };
            idx++;
        };
        Promise.allSettled(promises).then(() => {
            document.querySelector("#id_shasums").value = shasumsList.toString();
        });
    };


    // call: await sleep(ms)
    function sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    };


    // needs to be called a level up so that it can return the hash value
    async function MD5HashFile (file, idx) {
        return new Promise((resolve, reject) => {
            let spark  = new SparkMD5.ArrayBuffer();
            let reader = new ChunkedFileReader();

            reader.subscribe('chunk', function (e) {
                spark.append(e.chunk);
            });

            reader.subscribe('end', function (e) {
                let hash = spark.end();
                resolve(hash);
                //console.log(hash);
            });

            reader.readChunks(file);
        });
    };

};

