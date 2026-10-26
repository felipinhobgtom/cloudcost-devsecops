"use strict";

(() => {
  const slides = Array.from(document.querySelectorAll(".slide"));
  const controls = document.querySelector(".slide-controls");
  const previous = document.getElementById("previous");
  const next = document.getElementById("next");
  const status = document.getElementById("slide-status");
  const dotsContainer = document.getElementById("slide-dots");
  let currentIndex = 0;

  const dots = slides.map((slide, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.setAttribute("aria-label", `Ir para slide ${index + 1}: ${slide.dataset.title}`);
    button.setAttribute("aria-controls", slide.id);
    button.addEventListener("click", () => showSlide(index, true));
    dotsContainer.appendChild(button);
    return button;
  });

  function showSlide(index, updateHash) {
    currentIndex = Math.max(0, Math.min(index, slides.length - 1));
    slides.forEach((slide, slideIndex) => {
      const isCurrent = slideIndex === currentIndex;
      slide.hidden = !isCurrent;
      if (isCurrent) {
        dots[slideIndex].setAttribute("aria-current", "step");
      } else {
        dots[slideIndex].removeAttribute("aria-current");
      }
    });
    previous.disabled = currentIndex === 0;
    next.disabled = currentIndex === slides.length - 1;
    const number = String(currentIndex + 1).padStart(2, "0");
    status.textContent = `${number} / ${String(slides.length).padStart(2, "0")}`;
    status.setAttribute("aria-label", `Slide ${currentIndex + 1} de ${slides.length}: ${slides[currentIndex].dataset.title}`);
    document.title = `CloudCost — ${slides[currentIndex].dataset.title}`;
    if (updateHash) {
      window.history.replaceState(null, "", `#${slides[currentIndex].id}`);
    }
  }

  previous.addEventListener("click", () => showSlide(currentIndex - 1, true));
  next.addEventListener("click", () => showSlide(currentIndex + 1, true));
  document.getElementById("print").addEventListener("click", () => window.print());

  document.addEventListener("keydown", (event) => {
    if (event.altKey || event.ctrlKey || event.metaKey || event.defaultPrevented) return;
    const target = event.target;
    if (target instanceof HTMLElement && (target.isContentEditable || target.matches("input, textarea, select"))) return;
    if (event.key === " " && target instanceof Element && target.closest("a, button")) return;

    let destination;
    switch (event.key) {
      case "ArrowRight":
      case "ArrowDown":
      case "PageDown":
      case " ":
        destination = currentIndex + 1;
        break;
      case "ArrowLeft":
      case "ArrowUp":
      case "PageUp":
        destination = currentIndex - 1;
        break;
      case "Home":
        destination = 0;
        break;
      case "End":
        destination = slides.length - 1;
        break;
      case "p":
      case "P":
        event.preventDefault();
        window.print();
        return;
      default:
        return;
    }
    event.preventDefault();
    showSlide(destination, true);
  });

  window.addEventListener("hashchange", () => {
    const index = slides.findIndex((slide) => `#${slide.id}` === window.location.hash);
    if (index !== -1) showSlide(index, false);
  });

  const initialIndex = slides.findIndex((slide) => `#${slide.id}` === window.location.hash);
  showSlide(initialIndex === -1 ? 0 : initialIndex, false);
  document.body.classList.add("js-enabled");
  controls.hidden = false;
})();
