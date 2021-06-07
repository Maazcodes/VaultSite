window.onload = function () {
    document.querySelector("#id_dir_field").addEventListener("change", function() {
        files = document.querySelector("#id_dir_field").files;
        var directories = {};
        for (var file of files) {
            directories[file.name] = file.webkitRelativePath;
        }
    directories = JSON.stringify(directories);
    document.querySelector("#id_directories").value = directories
    });
}
