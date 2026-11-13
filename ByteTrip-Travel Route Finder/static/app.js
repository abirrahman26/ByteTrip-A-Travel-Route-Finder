document.getElementById("swap-button").addEventListener("click", () => {
    const start = document.getElementById("start");
    const end = document.getElementById("end");
    const selectedStart = start.value;
    start.value = end.value;
    end.value = selectedStart;
});