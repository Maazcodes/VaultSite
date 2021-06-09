var digipresDashboard = (function () {
    var fetching = 0;
    var initialized = false;
    var userId = "";
    var demoMode = false;
    var activeRequests = {};

    function isInitialized() {
        return initialized && fetching == 0;
    }

    onPageTransition.push(function () {
        for (let request of Object.values(activeRequests)) request.abort();
        activeRequests = {};
        chartalign.unregisterAll();
    });

    var regionDetails = {
        "us-west-1": {
            location: "300 Funston",
            radius: 10,
            country: "USA",
            fillKey: "regions",
            latitude: 37.782523,
            longitude: -130
        }, "us-west-2": {
            location: "2512 Florida",
            radius: 10,
            country: "USA",
            fillKey: "regions",
            latitude: 37.9292582,
            longitude: -122
        }, "eu-west-1": {
            location: "Amsterdam",
            radius: 10,
            country: "NL (Europe)",
            fillKey: "regions",
            latitude: 52.3546449,
            longitude: 4.8339212
        }, "ca-east-1": {
            location: "IAC",
            radius: 10,
            country: "Canada",
            fillKey: "regions",
            latitude: 45.4200567,
            longitude: -75.8479716
        }
    };

    function createWorldmap(regions) {
        chartalign.register("#worldmap .chart", function (width, height) {
            return $("<div style=\"position: relative; width: " + width + "px; height: " + height + "px;\"></div>");
        }, function ($el) {
            var bombMap = new Datamap({
                element: $el.get(0),
                scope: 'world',
                geographyConfig: {
                    popupOnHover: false,
                    highlightOnHover: false
                },
                fills: {
                    'countries': '#2a282c',
                    'regions': '#2991cc',
                    defaultFill: '#e3e7e8'
                },
                data: {
                    'USA': {fillKey: 'countries'},
                    'NLD': {fillKey: 'countries'}
                }
            });

            var bombs = [];
            for (let region of regions.reverse()) {
                let details = regionDetails[region];
                details.name = region;
                bombs.push(details);
            }

            bombMap.bubbles(bombs, {
                popupTemplate: function (geo, data) {
                    return ['<div class="hoverinfo">' + data.name,
                        '<br/>Location: ' + data.location + '',
                        '<br/>Country: ' + data.country + '',
                        '</div>'].join('');
                }
            });

            return bombMap;
        });
    }

    function createFilesEvolutionChart(labels, dataPoints) {
        chartalign.register("#temporal-scans-chart .chart", function (width, height) {
            return $("<canvas style=\"margin-top: -30px;\"></canvas>").attr("width", width).attr("height", height);
        }, function ($el) {
            return new Chart($el.get(0).getContext("2d"), {
                type: "line",
                data: {
                    labels: labels,
                    datasets: [{
                        label: "Files",
                        cubicInterpolationMode: "default",
                        lineTension: 0.3,
                        backgroundColor: "#2991cc",
                        borderColor: "#2480b4",
                        pointRadius: 0,
                        pointBackgroundColor: "#2991cc",
                        pointBorderColor: "#2991cc",
                        pointHoverRadius: 3,
                        pointHoverBackgroundColor: "#2991cc",
                        pointHoverBorderColor: "#2991cc",
                        pointHitRadius: 10,
                        pointBorderWidth: 2,
                        data: dataPoints
                    }]
                },
                options: {
                    title: {
                        display: true,
                        text: 'Files Evolution per Check'
                    },
                    maintainAspectRatio: false,
                    scales: {
                        xAxes: [{
                            time: {
                                unit: 'date'
                            },
                            gridLines: {
                                display: true,
                                drawBorder: false
                            },
                            ticks: {
                                maxTicksLimit: 7
                            }
                        }],
                        yAxes: [{
                            scaleLabel: {
                                display: false,
                                labelString: "Files"
                            },
                            ticks: {
                                maxTicksLimit: 5,
                                padding: 10,
                                callback: function (value, index, values) {
                                    return formatNumber(value, 1);
                                }
                            },
                            gridLines: {
                                color: "rgb(234, 236, 244)",
                                zeroLineColor: "rgb(234, 236, 244)",
                                drawBorder: false,
                                borderDash: [2],
                                zeroLineBorderDash: [2]
                            }
                        }]
                    },
                    legend: {
                        display: false
                    },
                    tooltips: {
                        backgroundColor: "rgb(255,255,255)",
                        bodyFontColor: "#858796",
                        titleMarginBottom: 10,
                        titleFontColor: '#6e707e',
                        titleFontSize: 14,
                        borderColor: '#dddfeb',
                        borderWidth: 1,
                        xPadding: 15,
                        yPadding: 15,
                        displayColors: false,
                        intersect: false,
                        mode: 'index',
                        caretPadding: 10,
                        callbacks: {
                            label: function (tooltipItem, chart) {
                                var datasetLabel = chart.datasets[tooltipItem.datasetIndex].label || '';
                                return datasetLabel + ': ' + formatNumber(tooltipItem.yLabel);
                            }
                        }
                    }
                }
            });
        }, function (chart) {
            chart.destroy();
        });
    }

    function createFilesRegionChart(regions, counts) {
        chartalign.register("#worldmap-histogram .chart", function (width, height) {
            return $("<canvas></canvas>").attr("width", width).attr("height", height);
        }, function ($el) {
            return new Chart($el.get(0), {
                type: 'bar',
                data: {
                    labels: regions,
                    datasets: [
                        {
                            label: "Files",
                            backgroundColor: ["#3e95cd", "#8e5ea2", "#3cba9f", "#e8c3b9", "#c45850"],
                            data: counts
                        }
                    ]
                },
                options: {
                    legend: {display: false},
                    title: {
                        display: true,
                        text: 'Files per Region'
                    }
                }
            });
        }, function (chart) {
            chart.destroy()
        });
    }

    function createCollectionsChart(collections, fileCounts) {
        chartalign.register("#collections-chart .chart", function (width, height) {
            return $("<canvas></canvas>").attr("width", width).attr("height", height);
        }, function ($el) {
            return new Chart($el.get(0), {
                type: 'doughnut',
                data: {
                    labels: collections,
                    datasets: [
                        {
                            label: "Collections",
                            backgroundColor: ["#3e95cd", "#8e5ea2", "#306ccd", "#a27698", "#21ba60", "#e8e6c5", "#c45850", "#3cba9f", "#e8c3b9", "#c45850"],
                            data: fileCounts
                        }
                    ]
                },
                options: {
                    legend: {display: false},
                    title: {
                        display: true,
                        text: 'Collections Distribution (%)'
                    }
                }
            });
        }, function (chart) {
            chart.destroy();
        });
    }

    function createFiletypesChart(fileTypes, counts) {
        chartalign.register("#filetypes-chart .chart", function (width, height) {
            return $("<canvas></canvas>").attr("width", width).attr("height", height);
        }, function ($el) {
            return new Chart($el.get(0), {
                type: 'doughnut',
                data: {
                    labels: fileTypes,
                    datasets: [
                        {
                            label: "File types",
                            backgroundColor: ["#3e95cd", "#8e5ea2", "#306ccd", "#a27698", "#21ba60", "#e8e6c5", "#c45850", "#3cba9f", "#e8c3b9", "#c45850"],
                            data: counts
                        }
                    ]
                },
                options: {
                    title: {
                        display: true,
                        text: 'File Types Distribution (%)'
                    }
                }
            });
        }, function (chart) {
            chart.destroy();
        });
    }

    var selectedCollectionId;
    function selectCollection(collectionId, $item) {
        if (isInitialized()) {
            $(".dashboard-list-collection").removeClass("selected");
            if (selectedCollectionId === collectionId) {
                selectedCollectionId = null;
                showReports();
                showStats();
                showFilesEvolutions();
                showSummary();
            } else {
                selectedCollectionId = collectionId;
                $item.addClass("selected");
                showReports(collectionId);
                showStats(collectionId);
                showFilesEvolutions(collectionId);
                showSummary(collectionId);
            }
            selectReport();
        }
    }

    var selectedReportCollectionId;
    var selectedReportId;
    function selectReport(collectionId, reportId, $item) {
        if (isInitialized()) {
            $(".dashboard-list-report").removeClass("selected");
            if (selectedReportCollectionId === collectionId && selectedReportId === reportId) {
                selectedReportCollectionId = null;
                selectedReportId = null;
                showStats(selectedCollectionId);
                showSummary(selectedCollectionId);
            } else {
                selectedReportCollectionId = collectionId;
                selectedReportId = reportId;
                if ($item) $item.addClass("selected");
                if (collectionId && reportId) fetchReportSummary(collectionId, reportId);
            }
        }
    }

    function fetchCollections() {
        var $spinner = $("#dashboard-collections .spinner");
        var url = "/api/collections" + (demoMode ? "?demo=true" : "");
        fetching += 1;
        activeRequests[url] = $.getJSON(url, function (json) {
            $spinner.hide();
            var $container = $("#dashboard-collections .dashboard-list");
            $container.empty();
            for (let collection of json.collections) {
                let $item = $("<div>").addClass("dashboard-list-item dashboard-list-collection").append([
                    $("<span>").text(collection.id),
                    $("<span>").addClass("dashboard-list-item-sub").text(" (" + collection.name + ")"),
                ]).click(function () {
                    selectCollection(collection.id, $item);
                });
                $container.append($item);
            }
            fetching -= 1;
        });
    }

    var allReports = [];
    var collectionReports = {};

    function showReports(collectionId) {
        var reports = (collectionId && (collectionReports[collectionId] || [])) || allReports;
        var $container = $("#dashboard-reports .dashboard-list");
        $container.empty();
        for (let report of reports) {
            let split = report.id.split("T");
            let label = split[0] + " " + split[1].substr(0, 8).replace(/-/g, ":");
            let $item = $("<div>").addClass("dashboard-list-item dashboard-list-report").append([
                $("<span>").text(label),
                $("<span>").addClass("dashboard-list-item-sub").text(" (" + report.collection + ")"),
            ]).click(function () {
                selectReport(report.collection, report.id, $item);
            });
            $container.append($item);
        }
    }

    function fetchReports() {
        var url = "/api/reports" + (demoMode ? "?demo=true" : "");
        fetching += 1;
        activeRequests[url] = $.getJSON(url, function (json) {
            for (let report of json.reports) {
                collectionReports[report.collection] = collectionReports[report.collection] || [];
                collectionReports[report.collection].push(report);
            }
            allReports = json.reports;
            showReports();
            $("#dashboard-reports .spinner").hide();
            fetching -= 1;
        });
    }

    function loadStats(selectors) {
        var containers = [];
        for (let selector of selectors) {
            var $container = $(selector);
            var $content = $container.children(".stats-content");
            var $spinner = $container.children(".spinner");
            $content.hide();
            $spinner.show();
            containers.push($container);
        }
        return containers;
    }

    function readyStats(containers) {
        for (let $container of containers) {
            var $content = $container.children(".stats-content");
            var $spinner = $container.children(".spinner");
            $spinner.hide();
            $content.show();
        }
    }

    var accountStats = {};
    var collectionsStats = {};

    function showStats(collectionId) {
        var collectionStats = (collectionId && collectionsStats[collectionId]);
        var stats = collectionStats || accountStats;
        var latest = stats.recentReport || stats || {};

        if (collectionStats) {
            $("#dashboard-statistics-title").empty().append([
                $("<span>").text("Collection Statistics"),
                " (",
                $("<a>").attr("href", "/ait/" + userId + "/digipres/collections/" + collectionId + (demoMode ? "?demo=true" : "")).text("browse"),
                ")"
            ]);
        } else {
            $("#dashboard-statistics-title").text("Account Statistics");
        }

        $("#dashboard-stats-files .stats-value").text(formatNumber(stats.fileCount || 0));
        $("#dashboard-stats-size .stats-value").text(formatBytes(stats.totalSize || 0));

        if (latest.latestReport) {
            $("#dashboard-report-title").empty().append([
                $("<span>").text("Recent Fixity Report"),
                " (",
                $("<a>").attr("href", "/ait/" + userId + "/digipres/reports/" + latest.id + "/" + latest.latestReport + (demoMode ? "?demo=true" : "")).text("show"),
                ")"
            ]);
        } else {
            $("#dashboard-report-title").text("Recent Fixity Report");
        }

        $("#dashboard-stats-report-date .stats-value").text((latest.time || "N/A").substr(0, 10));
        $("#dashboard-stats-report-errors .stats-value").text(formatNumber(latest.errorCount || 0));
        $("#dashboard-stats-report-files .stats-value").text(formatNumber(latest.fileCount || 0));
        $("#dashboard-stats-report-size .stats-value").text(formatBytes(latest.totalSize || 0));
    }

    function fetchStats() {
        var loadContainers = loadStats(["#dashboard-stats-files", "#dashboard-stats-size", "#dashboard-stats-report-date", "#dashboard-stats-report-errors", "#dashboard-stats-report-files", "#dashboard-stats-report-size"]);

        var url = "api/collections_stats" + (demoMode ? "?demo=true" : "");
        fetching += 1;
        activeRequests[url] = $.getJSON(url, function (json) {
            var latest;

            accountStats = {};
            for (let collection of json.collections) {
                collectionsStats[collection.id] = collection;
                if (collection.latestReport && (!latest || collection.latestReport > latest.latestReport)) latest = collection;
                accountStats.fileCount = (accountStats.fileCount || 0) + (collection.fileCount || 0);
                accountStats.totalSize = (accountStats.totalSize || 0) + (collection.totalSize || 0);
            }

            accountStats.recentReport = latest;

            showStats();
            readyStats(loadContainers);
            fetching -= 1;
        });
    }


    var accountFilesEvolution = {};
    function showFilesEvolutions(collectionId) {
        if (collectionId) {
            fetchFilesEvolutions(collectionId);
        } else {
            createFilesEvolutionChart(accountFilesEvolution.labels, accountFilesEvolution.dataPoints);
        }
    }

    var months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    function fetchFilesEvolutions(collectionId) {
        var $filesEvolutionChart = $("#temporal-scans-chart .chart");
        $filesEvolutionChart.hide();
        var $filesEvolutionChartSpinner = $("#temporal-scans-chart .spinner");
        $filesEvolutionChartSpinner.show();

        var url = "/api/reports_files" + (collectionId ? "/" + collectionId : "") + (demoMode ? "?demo=true" : "");
        fetching += 1;
        activeRequests[url] = $.getJSON(url, function (json) {
            var labels = [];
            var dataPoints = [];
            var collectionsFiles = {};
            for (let report of json.reports) {
                collectionsFiles[report.collection] = report.fileCount;
                let totalFileCount = 0;
                for (let fileCount of Object.values(collectionsFiles)) totalFileCount += fileCount;
                dataPoints.push(totalFileCount);
                let year = report.id.substr(2, 2);
                let month = months[parseInt(report.id.substr(5, 2)) - 1];
                labels.push(month + " " + parseInt(report.id.substr(8, 2)) + ", " + year);
            }
            if (labels.length === 1) {
                labels.push(labels[0]);
                dataPoints.push(dataPoints[0]);
            }
            if (!collectionId) {
                accountFilesEvolution.labels = labels;
                accountFilesEvolution.dataPoints = dataPoints;
            }

            $filesEvolutionChartSpinner.hide();
            $filesEvolutionChart.show();
            createFilesEvolutionChart(labels, dataPoints);

            fetching -= 1;
        });
    }

    var accountSummary = {};
    var collectionsSummary = {};

    function showSummary(collectionId) {
        var summary = (collectionId && collectionsSummary[collectionId]) || accountSummary;

        $("#dashboard-stats-repl .stats-value").text(formatNumber(summary.avgReplication || 0, 2));
        $("#dashboard-stats-regions .stats-value").text(formatNumber(Object.keys(summary.regions || {}).length));

        createFiletypesChart(Object.keys(summary.fileTypes || {}), Object.values(summary.fileTypes || {}));
        createWorldmap(Object.keys(summary.regions || {}));
        createFilesRegionChart(Object.keys(summary.regions || {}), Object.values(summary.regions || {}));
    }

    function fetchSummaries() {
        var $collectionsChart = $("#collections-chart .chart");
        $collectionsChart.hide();

        var $filetypesChart = $("#filetypes-chart .chart");
        $filetypesChart.hide();
        var $filetypesChartSpinner = $("#filetypes-chart .spinner");
        $filetypesChartSpinner.show();

        var $worldMap = $("#worldmap .chart");
        $worldMap.hide();
        var $worldMapSpinner = $("#worldmap .spinner");
        $worldMapSpinner.show();

        var $filesRegionChart = $("#worldmap-histogram .chart");
        $filesRegionChart.hide();
        var $filesRegionChartSpinner = $("#worldmap-histogram .spinner");
        $filesRegionChartSpinner.show();

        var loadContainers = loadStats(["#dashboard-stats-repl", "#dashboard-stats-regions"]);

        var url = "/api/collections_summary" + (demoMode ? "?demo=true" : "");
        fetching += 1;
        activeRequests[url] = $.getJSON(url, function (json) {
            var collections = [];
            var fileCounts = [];
            var filesTotal = 0;
            var weightedReplAvgSum = 0.0;
            var fileTypes = {};
            var regions = {};

            for (let collection of json.collections) {
                collectionsSummary[collection.id] = collection;
                collections.push(collection.id);
                fileCounts.push(collection.fileCount || 1);
                filesTotal += collection.fileCount || 0;
                weightedReplAvgSum += ((collection.avgReplication || 0) * (collection.fileCount || 0));
                for (let fileType of Object.keys(collection.fileTypes || {})) {
                    fileTypes[fileType] = (fileTypes[fileType] || 0) + collection.fileTypes[fileType];
                }
                for (let region of Object.keys(collection.regions || {})) {
                    regions[region] = (regions[region] || 0) + collection.regions[region];
                }
            }

            accountSummary.fileTypes = fileTypes;
            accountSummary.regions = regions;
            accountSummary.avgReplication = filesTotal > 0 ? weightedReplAvgSum / filesTotal : 0;

            $("#collections-chart .spinner").hide();
            $collectionsChart.show();
            createCollectionsChart(collections, fileCounts);

            $filetypesChartSpinner.hide();
            $filetypesChart.show();
            $worldMapSpinner.hide();
            $worldMap.show();
            $filesRegionChartSpinner.hide();
            $filesRegionChart.show();

            showSummary();

            readyStats(loadContainers);

            fetching -= 1;
        });
    }

    function fetchReportSummary(collectionId, reportId) {
        $("#dashboard-report-title").empty().append([
            $("<span>").text("Report Statistics"),
            " (",
            $("<a>").attr("href", "/ait/" + userId + "/digipres/reports/" + collectionId + "/" + reportId + (demoMode ? "?demo=true" : "")).text("show"),
            ")"
        ]);

        var $filetypesChart = $("#filetypes-chart .chart");
        $filetypesChart.hide();
        var $filetypesChartSpinner = $("#filetypes-chart .spinner");
        $filetypesChartSpinner.show();

        var $worldMap = $("#worldmap .chart");
        $worldMap.hide();
        var $worldMapSpinner = $("#worldmap .spinner");
        $worldMapSpinner.show();

        var $filesRegionChart = $("#worldmap-histogram .chart");
        $filesRegionChart.hide();
        var $filesRegionChartSpinner = $("#worldmap-histogram .spinner");
        $filesRegionChartSpinner.show();

        var loadContainers = loadStats(["#dashboard-stats-report-date", "#dashboard-stats-report-errors", "#dashboard-stats-report-files", "#dashboard-stats-report-size"]);

        var url = "/api/report_summary/" + collectionId + "/" + reportId + (demoMode ? "?demo=true" : "");
        fetching += 1;
        activeRequests[url] = $.getJSON(url, function (report) {
            $("#dashboard-stats-report-date .stats-value").text((report.id || "").substr(0, 10));
            $("#dashboard-stats-report-errors .stats-value").text(formatNumber(report.errorCount || 0));
            $("#dashboard-stats-report-files .stats-value").text(formatNumber(report.fileCount || 0));
            $("#dashboard-stats-report-size .stats-value").text(formatBytes(report.totalSize || 0));

            readyStats(loadContainers);

            $filetypesChartSpinner.hide();
            $filetypesChart.show();
            createFiletypesChart(Object.keys(report.fileTypes), Object.values(report.fileTypes));

            $worldMapSpinner.hide();
            $worldMap.show();
            createWorldmap(Object.keys(report.regions));

            $filesRegionChartSpinner.hide();
            $filesRegionChart.show();
            createFilesRegionChart(Object.keys(report.regions), Object.values(report.regions));

            fetching -= 1;
        });
    }

    function init(user, demo) {
        userId = user;
        demoMode = demo;
        Chart.defaults.global.defaultFontFamily = 'Nunito,-apple-system,system-ui,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif';
        Chart.defaults.global.defaultFontColor = '#858796';
        fetchCollections();
        fetchReports();
        fetchStats();
        fetchFilesEvolutions();
        fetchSummaries();
        initialized = true;
    }

    return {
        init: init
    }
})();