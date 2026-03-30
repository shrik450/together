// JS only toggles aria-expanded; CSS adjacent-sibling rules handle dropdown visibility.
document.querySelectorAll(".breadcrumb-item").forEach((item) => {
  const trigger = item.querySelector(".breadcrumb-trigger");
  const dropdown = item.querySelector(".breadcrumb-dropdown");

  if (!trigger || !dropdown) return;

  trigger.addEventListener("click", (e) => {
    e.preventDefault();
    const isOpen = trigger.getAttribute("aria-expanded") === "true";

    document
      .querySelectorAll('.breadcrumb-trigger[aria-expanded="true"]')
      .forEach((other) => {
        if (other !== trigger) {
          other.setAttribute("aria-expanded", "false");
        }
      });

    trigger.setAttribute("aria-expanded", !isOpen);
  });
});

document.querySelectorAll(".topbar-user").forEach((item) => {
  const trigger = item.querySelector(".topbar-user-trigger");
  const dropdown = item.querySelector(".topbar-user-dropdown");

  if (!trigger || !dropdown) return;

  trigger.addEventListener("click", (e) => {
    e.preventDefault();
    const isOpen = trigger.getAttribute("aria-expanded") === "true";
    trigger.setAttribute("aria-expanded", !isOpen);
  });
});

document.addEventListener("click", (e) => {
  if (!e.target.closest(".breadcrumb-item")) {
    document
      .querySelectorAll('.breadcrumb-trigger[aria-expanded="true"]')
      .forEach((trigger) => {
        trigger.setAttribute("aria-expanded", "false");
      });
  }
  if (!e.target.closest(".topbar-user")) {
    document
      .querySelectorAll('.topbar-user-trigger[aria-expanded="true"]')
      .forEach((trigger) => {
        trigger.setAttribute("aria-expanded", "false");
      });
  }
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    document
      .querySelectorAll('.breadcrumb-trigger[aria-expanded="true"]')
      .forEach((trigger) => {
        trigger.setAttribute("aria-expanded", "false");
      });
    document
      .querySelectorAll('.topbar-user-trigger[aria-expanded="true"]')
      .forEach((trigger) => {
        trigger.setAttribute("aria-expanded", "false");
      });
  }
});
