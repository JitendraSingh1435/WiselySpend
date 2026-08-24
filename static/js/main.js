// main.js — students will add JavaScript here as features are built

(function () {
    const openBtn = document.getElementById("demo-modal-open");
    const overlay = document.getElementById("demo-modal-overlay");
    const closeBtn = document.getElementById("demo-modal-close");
    const video = document.getElementById("demo-modal-video");

    if (!openBtn || !overlay || !closeBtn || !video) return;

    function openModal() {
        video.src = video.dataset.src;
        overlay.hidden = false;
    }

    function closeModal() {
        overlay.hidden = true;
        video.src = "";
    }

    openBtn.addEventListener("click", openModal);
    closeBtn.addEventListener("click", closeModal);

    overlay.addEventListener("click", function (event) {
        if (event.target === overlay) {
            closeModal();
        }
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && !overlay.hidden) {
            closeModal();
        }
    });
})();
