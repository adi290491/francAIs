() => {
  // Workaround for Gradio 6.30's microphone recorder: it renders a "Select input device"
  // dropdown (select.mic-select) but never reads it. Recording always calls
  // getUserMedia({audio: true}), so the browser default mic is used whatever is selected
  // (e.g. a phone chosen in the list records from the laptop instead).
  // This makes audio getUserMedia calls use the device the user picked in that dropdown.
  if (window.__frenchTutorMicDeviceFix) return;
  window.__frenchTutorMicDeviceFix = true;

  const media = navigator.mediaDevices;
  if (!media || typeof media.getUserMedia !== "function") return;

  // Only override once the user has actually picked a device, so the browser default is
  // kept for anyone who never touches the dropdown.
  document.addEventListener(
    "change",
    (event) => {
      const el = event.target;
      if (el instanceof HTMLSelectElement && el.classList.contains("mic-select")) {
        el.dataset.userChosen = "true";
      }
    },
    true,
  );

  const chosenDeviceId = () => {
    const picked = [...document.querySelectorAll("select.mic-select[data-user-chosen]")].filter(
      (el) => el.value,
    );
    const visible = picked.find((el) => el.offsetParent !== null);
    return (visible || picked[0] || {}).value || null;
  };

  const original = media.getUserMedia.bind(media);
  media.getUserMedia = async (constraints) => {
    const deviceId = chosenDeviceId();
    const audio = constraints && constraints.audio;
    const callerChoseDevice = audio && typeof audio === "object" && audio.deviceId;
    if (!deviceId || !audio || callerChoseDevice) return original(constraints);

    const base = typeof audio === "object" ? audio : {};
    try {
      return await original({ ...constraints, audio: { ...base, deviceId: { exact: deviceId } } });
    } catch (error) {
      // The device was unplugged or disconnected since it was listed: fall back to the default.
      console.warn("Selected microphone is unavailable; using the default one.", error);
      return original(constraints);
    }
  };
}
