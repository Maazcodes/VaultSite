window.onload = function () {
    document.querySelector("#id_dir_field").addEventListener("change", function() {
        document.querySelector("#id_file_field").disabled = true;
        let directories = [];
        let sizes       = [];
        let files = document.querySelector("#id_dir_field").files;
        for (var file of files) {
            directories.push(file.webkitRelativePath);
            sizes.push(file.size);
        }
        document.querySelector("#id_directories").value = directories.toString();
        document.querySelector("#id_sizes").value = sizes.toString();
        doSomeSums(files);
    });


    document.querySelector("#id_file_field").addEventListener("change", function() {
        document.querySelector("#id_dir_field").disabled = true;
        let directories = [];
        let sizes       = [];
        let files = document.querySelector("#id_file_field").files;
        for (var file of files) {
            directories.push(file.name);
            sizes.push(file.size);
        }
        document.querySelector("#id_directories").value = directories.toString();
        document.querySelector("#id_sizes").value = sizes.toString();
        doSomeSums(files);
    });


    const form = document.querySelector('form')
    form.addEventListener('submit', event => {
        event.preventDefault();
        // It amazes me that the shasums are available!
        XHRuploadFiles(form);
    })

    function formatBytes(bytes, decimals = 2) {
        if (bytes === 0) return '0 Bytes';
    
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];
    
        const i = Math.floor(Math.log(bytes) / Math.log(k));
    
        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    }

    async function XHRuploadFiles (form) {
        let total_size = 0;
        let num_files  = 0;
        start = performance.now();

        let collection = document.querySelector("#id_collection").value;
        let comment    = document.querySelector("#id_comment").value;

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
            xhr.open('POST', '/vault/deposit/web', true);

            xhr.onerror = function () {
                console.error('<b>Request Failed: Network Error.</b>');
            };

            xhr.onabort = function () {
                console.error('<b>Request Aborted.</b>');
            };

            xhr.upload.onprogress = function(e) {
                if (e.lengthComputable) {
                    let progress = Math.round((e.loaded / e.total)*100);
                    document.querySelector('#progress_bar').value = progress;
                };
            };

            xhr.onloadend = function() {
                let end = performance.now();
                let runtime = ((end - start) / 1000).toFixed(2);
                start = end;
                let msg = "";
                msg += ' Files transfered: ' + num_files + ',';
                msg += ' Size: ' + formatBytes(total_size);
                msg += ' and Runtime: ' + runtime + 's';
                document.querySelector('#stats').innerHTML += '<pre>' + msg + '</pre>'
                console.log(msg);
                console.log(xhr.response);
                resetForm();
            };

            xhr.send(data);
    }

    function resetForm() {
        form.reset()
        document.querySelector("#id_file_field").disabled = false;
        document.querySelector("#id_dir_field").disabled = false;
        document.querySelector('#progress_bar').value = 0;
    }

    shasumsGlobal = [];
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
        }
        return hexBytes.join("");
    }


    async function sha256HashFile(file, idx) {
        let buffer = await file.arrayBuffer();
        return crypto.subtle.digest("SHA-256", buffer).then(function (hash) {
            shasumsGlobal[idx] = bytesToHexString(hash);
        });
    };

    async function doSomeSums(files) {
        let tooBig = 1024*1024*1024;
        let promises = [];
        let idx = 0;
        shasumsGlobal = [];
        for (var file of files) {
            if (file.size < tooBig) {
                promises.push(sha256HashFile(file, idx));
            } else {
                shasumsGlobal[idx] = 'DEADBEEF';
            }
            idx++;
        };
        Promise.allSettled(promises).then(() => {
            document.querySelector("#id_shasums").value = shasumsGlobal.toString();
        });
    };
}

