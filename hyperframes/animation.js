const slideRoot = document.getElementById('slide');
const caption = document.getElementById('caption');
const playButton = document.getElementById('play');
const subtitleButton = document.getElementById('subtitles');
let subtitlesOn = true;

subtitleButton.addEventListener('click', () => {
  subtitlesOn = !subtitlesOn;
  subtitleButton.textContent = subtitlesOn ? 'Subtitles On' : 'Subtitles Off';
  caption.classList.toggle('on', subtitlesOn);
});

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function loadProject() {
  const res = await fetch('project.json');
  return res.json();
}

function layerPath(slideNumber, name) {
  return `../output/slide_${String(slideNumber).padStart(2, '0')}/${name}`;
}

function audioPath(slideNumber) {
  return `../audio/slide_${String(slideNumber).padStart(2, '0')}_voiceover.mp3`;
}

function showSlide(slide, timing) {
  slideRoot.innerHTML = '';
  const base = document.createElement('img');
  base.className = 'bg';
  base.src = layerPath(slide.slide, 'background.png');
  slideRoot.appendChild(base);
  for (const layer of slide.layers) {
    const img = document.createElement('img');
    img.className = `layer ${layer.animation}`;
    img.src = layerPath(slide.slide, layer.name);
    img.style.left = `${layer.x / slide.width * 100}%`;
    img.style.top = `${layer.y / slide.height * 100}%`;
    img.style.width = `${layer.width / slide.width * 100}%`;
    img.style.height = `${layer.height / slide.height * 100}%`;
    img.style.zIndex = layer.z_index;
    img.style.setProperty('--dur', `${layer.duration}s`);
    slideRoot.appendChild(img);
    window.setTimeout(() => img.classList.add('show'), layer.start * 1000);
  }
  caption.textContent = timing.script;
  caption.classList.toggle('on', subtitlesOn);
}

async function play() {
  playButton.disabled = true;
  const project = await loadProject();
  for (const slide of project.slides) {
    const key = `slide_${String(slide.slide).padStart(2, '0')}`;
    const timing = project.timing[key];
    showSlide(slide, timing);
    const audio = new Audio(audioPath(slide.slide));
    audio.volume = 1;
    try { await audio.play(); } catch (e) {}
    await sleep(slide.duration * 1000);
    await sleep(500);
  }
  playButton.disabled = false;
}

playButton.addEventListener('click', play);
loadProject().then(project => showSlide(project.slides[0], project.timing.slide_01));
