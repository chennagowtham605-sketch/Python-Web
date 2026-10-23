(function () {
  var reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  var inputRippleTimers = new WeakMap();
  var buttonRipples = new WeakMap();
  var buttonSelector = [
    "button",
    'input[type="button"]',
    'input[type="submit"]',
    'input[type="reset"]',
    "a.btn",
    "a.btn-secondary",
    "a.btn-primary",
    "a.btn-danger",
    "a.btn-export",
    "a.back-link",
    "a.footer-admin-link",
    'a[role="button"]',
    "nav a.cta",
    "header a.cta"
  ].join(",");

  document.addEventListener("click", function (event) {
    var target = event.target;
    if (!(target instanceof Element) || reducedMotion.matches) return;

    var button = target.closest(buttonSelector);
    if (!button || button.matches(":disabled, [aria-disabled='true']")) return;

    var bounds = button.getBoundingClientRect();
    var x = event.detail === 0 ? bounds.width / 2 : event.clientX - bounds.left;
    var y = event.detail === 0 ? bounds.height / 2 : event.clientY - bounds.top;
    var size = Math.ceil(Math.hypot(
      Math.max(x, bounds.width - x),
      Math.max(y, bounds.height - y)
    ) * 2);
    var left = x - size / 2;
    var top = y - size / 2;

    if (button instanceof HTMLInputElement) {
      window.clearTimeout(inputRippleTimers.get(button));
      button.classList.remove("button-fx-input-ripple");
      button.style.setProperty("--ripple-size", size + "px");
      button.style.setProperty("--ripple-left", left + "px");
      button.style.setProperty("--ripple-top", top + "px");
      void button.offsetWidth;
      button.classList.add("button-fx-input-ripple");
      inputRippleTimers.set(button, window.setTimeout(function () {
        button.classList.remove("button-fx-input-ripple");
        button.style.removeProperty("--ripple-size");
        button.style.removeProperty("--ripple-left");
        button.style.removeProperty("--ripple-top");
        inputRippleTimers.delete(button);
      }, 650));
      return;
    }

    var previousRipple = buttonRipples.get(button);
    if (previousRipple) previousRipple.remove();

    var ripple = document.createElement("span");

    ripple.className = "button-fx-ripple";
    ripple.setAttribute("aria-hidden", "true");
    ripple.style.setProperty("--ripple-size", size + "px");
    ripple.style.setProperty("--ripple-x", left + "px");
    ripple.style.setProperty("--ripple-y", top + "px");
    button.appendChild(ripple);
    buttonRipples.set(button, ripple);
    ripple.addEventListener("animationend", function () {
      ripple.remove();
      if (buttonRipples.get(button) === ripple) buttonRipples.delete(button);
    }, { once: true });
  });
})();
