(() => {
    const overlay = document.getElementById('loadingOverlay');
    if (!overlay) {
        return;
    }

    document.addEventListener('submit', (event) => {
        const form = event.target;
        if (!(form instanceof HTMLFormElement)) {
            return;
        }

        const confirmMessage = form.dataset.confirmMessage;
        if (confirmMessage && !window.confirm(confirmMessage)) {
            event.preventDefault();
            return;
        }

        overlay.classList.add('is-visible');
    });
})();
