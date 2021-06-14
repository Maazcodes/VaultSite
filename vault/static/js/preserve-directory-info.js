
window.onload = function () {
    document.querySelector("#id_dir_field").addEventListener("change", function() {
        let directories = [];
        let files = document.querySelector("#id_dir_field").files;
        for (var file of files) {
            directories.push(file.webkitRelativePath);
        }
        document.querySelector("#id_directories").value = directories.toString();
    });

    document.querySelector("#id_file_field").addEventListener("change", function() {
        let directories = [];
        let files = document.querySelector("#id_file_field").files;
        for (var file of files) {
            directories.push(file.name);
        }
        document.querySelector("#id_directories").value = directories.toString();
    });


    document.querySelector("#id_collection").addEventListener("change", function() {
        let e = document.querySelector("#id_collection");
        let collname = e.options[e.selectedIndex].text;
        document.querySelector("#id_collname").value = collname;
    });
}

