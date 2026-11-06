/* Natural content height only. No storage or same-origin APIs. */
const postHeight = () => parent.postMessage({ abstractsHeight: Math.ceil(document.body.getBoundingClientRect().height) }, '*');
addEventListener('load', postHeight);
new ResizeObserver(postHeight).observe(document.body);
addEventListener('resize', postHeight);
if (document.fonts) document.fonts.ready.then(postHeight);

const motionButton = document.querySelector('.motion-toggle');
motionButton.addEventListener('click', () => {
  const paused = motionButton.getAttribute('aria-pressed') !== 'true';
  document.body.dataset.motion = paused ? 'paused' : 'playing';
  motionButton.setAttribute('aria-pressed', String(paused));
  motionButton.textContent = paused ? 'Resume motion' : 'Pause motion';
  motionButton.setAttribute('aria-label', `${paused ? 'Resume' : 'Pause'} the animated flashlight and film grain`);
});
