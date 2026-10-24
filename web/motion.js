(() => {
  if (!window.gsap || !window.Lenis) return;

  const lenis = new Lenis({
    duration: 1.05,
    smoothWheel: true,
    syncTouch: false,
    wheelMultiplier: 0.8,
  });
  window.campusChakraLenis = lenis;
  lenis.on('scroll', () => window.ScrollTrigger?.update());

  window.gsap.ticker.add((time) => lenis.raf(time * 1000));
  window.gsap.ticker.lagSmoothing(0);

  if (window.ScrollTrigger) {
    window.gsap.registerPlugin(window.ScrollTrigger);
  }

  const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  if (reduced) return;

  const splash = document.getElementById('splashScreen');
  const hero = document.querySelector('.hero-glass-section');
  const nav = document.getElementById('heroGlassNavbar');
  const copy = document.querySelector('.hero-center-content');
  const cards = document.querySelectorAll('.glass-card');

  if (splash) {
    window.gsap.fromTo(splash.querySelectorAll('.splash-brand-pill, .splash-enter-btn'),
      { y: 14, opacity: 0 },
      { y: 0, opacity: 1, duration: 0.65, stagger: 0.12, ease: 'power3.out', delay: 0.25 });
  }
  if (nav) window.gsap.from(nav, { y: -18, opacity: 0, duration: 0.65, ease: 'power3.out', delay: 0.12 });
  if (copy) window.gsap.from(copy.children, { y: 26, opacity: 0, duration: 0.72, stagger: 0.1, ease: 'power3.out', delay: 0.22 });
  if (cards.length) window.gsap.from(cards, { y: 32, opacity: 0, duration: 0.65, stagger: 0.08, ease: 'power3.out', delay: 0.4 });

  if (hero && window.ScrollTrigger) {
    window.gsap.to(hero.querySelectorAll('.hero-ambient-glow'), {
      yPercent: 15,
      ease: 'none',
      scrollTrigger: { trigger: hero, start: 'top top', end: 'bottom top', scrub: 0.5 },
    });
  }
})();
