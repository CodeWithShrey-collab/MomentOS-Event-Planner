import { useEffect, useRef, useState, type CSSProperties } from 'react';
import { Link } from 'react-router-dom';
import { ArrowDown, ArrowRight, ArrowUpRight, Check, ChevronLeft, ChevronRight, CircleDot } from 'lucide-react';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { useGSAP } from '@gsap/react';
import { Brand } from '../components/AppShell';
import { TYPE_COPY } from '../data/demoData';
import type { EventType } from '../types';
import { demoApi } from '../services/demoApi';

gsap.registerPlugin(ScrollTrigger, useGSAP);

const gallery = [
  { type: 'wedding' as EventType, src: '/images/wedding-garden.webp', alt: 'A reception table dressed with flowers and place settings', guests: '150 guests' },
  { type: 'birthday' as EventType, src: '/images/birthday-table.webp', alt: 'Colorful balloons gathered for a birthday celebration', guests: '60 guests' },
  { type: 'community' as EventType, src: '/images/community-gathering.webp', alt: 'Friends gathered together at sunset', guests: '300 people' },
];

const principles = [
  {
    label: 'A plan you can question',
    title: 'See what a change touches before it becomes a decision.',
    detail: 'Ripple previews show budget, capacity, and task effects. Your current plan stays put until you confirm.',
    tone: 'navy',
  },
  {
    label: 'Numbers with their assumptions',
    title: 'Every estimate stays visible, editable, and in context.',
    detail: 'Planning assumptions are clearly marked. Your entered amounts and quotations remain distinct.',
    tone: 'cobalt',
  },
  {
    label: 'A useful role for AI',
    title: 'Personal ideas help. Deterministic math decides the totals.',
    detail: 'GPT-6 Luna helps shape and explain a plan; MomentOS calculates budgets and dependencies.',
    tone: 'paper',
  },
];

export function LandingPage() {
  const [ownedEvents, setOwnedEvents] = useState<{ id: string; title: string }[]>([]);
  const [activePrinciple, setActivePrinciple] = useState(0);
  useEffect(() => {
    let active = true;
    demoApi.listEvents().then((response) => { if (active) setOwnedEvents(response.data); }).catch(() => { if (active) setOwnedEvents([]); });
    return () => { active = false; };
  }, []);

  const pageRef = useRef<HTMLDivElement>(null);
  useGSAP(() => {
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduceMotion) return;

    gsap.fromTo('.hero-copy > *', { y: 28, opacity: 0 }, {
      y: 0, opacity: 1, duration: 0.7, stagger: 0.09, ease: 'power2.out', clearProps: 'all',
    });

    gsap.utils.toArray<HTMLElement>('.reveal-image').forEach((image) => {
      gsap.fromTo(image, { scale: 0.92, opacity: 0.62 }, {
        scale: 1, opacity: 1, ease: 'none',
        scrollTrigger: { trigger: image, start: 'top 88%', end: 'bottom 15%', scrub: true },
      });
    });

    gsap.fromTo('.desire-copy span', { opacity: 0.12 }, {
      opacity: 1, stagger: 0.055, ease: 'none',
      scrollTrigger: { trigger: '.desire-copy', start: 'top 74%', end: 'bottom 38%', scrub: true },
    });

    gsap.fromTo('.promise-card', { y: 84, scale: 0.94, opacity: 0.55 }, {
      y: 0, scale: 1, opacity: 1, stagger: 0.12, ease: 'none',
      scrollTrigger: { trigger: '.principles-section', start: 'top 86%', end: 'center 48%', scrub: 0.6 },
    });
  }, { scope: pageRef });

  const movePrinciple = (step: number) => {
    setActivePrinciple((index) => (index + step + principles.length) % principles.length);
  };

  return (
    <div className="landing studio-landing" ref={pageRef}>
      <div className="landing-nav-wrap"><header className="landing-nav">
        <Brand />
        <nav aria-label="Main navigation"><a href="#moments">The workspace</a><a href="#event-types">Your event</a><a href="#how-it-works">How it works</a></nav>
        <div className="landing-nav-actions">
          {import.meta.env.VITE_MOMENTOS_MODE === 'demo' ? <Link to="/events/moment-wedding-01" className="nav-signin">Explore demo</Link> : ownedEvents[0] ? <Link to={`/events/${ownedEvents[0].id}`} className="nav-signin">My events</Link> : null}
          <Link to="/events/new" className="button button-primary button-small">Start planning <ArrowRight size={15} /></Link>
        </div>
      </header></div>

      <main className="landing-main">
        <section className="hero-section studio-hero" aria-labelledby="hero-title">
          <div className="hero-copy">
            <p className="eyebrow hero-eyebrow"><span className="eyebrow-line" /> A better way to bring it together</p>
            <h1 id="hero-title"><span>Plan every detail.</span><span className="hero-title-accent">Keep the moment.</span></h1>
            <p className="hero-description">Budgets, people, timing, and the hundred small decisions — all held in one plan that can move with your celebration.</p>
            <div className="hero-actions">
              <Link to="/events/new" className="button button-primary button-large">Start planning <ArrowRight size={18} /></Link>
              <a href="#moments" className="button button-secondary button-large">Explore the workspace <ArrowDown size={16} /></a>
            </div>
            <div className="hero-note"><span className="hero-note-rule" /><span>Weddings, birthdays, and community gatherings — planned around real life.</span></div>
          </div>
          <figure className="hero-art" aria-label="An intimate garden celebration at golden hour">
            <img className="hero-image reveal-image" src="/images/celebration-hero.webp" alt="A couple celebrating their wedding with a bouquet at golden hour" />
            <div className="hero-image-wash" />
            <figcaption className="hero-art-label"><span>THE DAY IS THE POINT</span><strong>Everything else, in good order.</strong></figcaption>
          </figure>
          <a className="scroll-cue" href="#moments"><span className="scroll-cue-line" /> A plan with room for life <ArrowDown size={14} /></a>
        </section>

        <section className="marquee-section studio-marquee" aria-hidden="true">
          <div className="marquee-track" aria-hidden="true">{['The people', 'The plan', 'The little details', 'The moments'].concat(['The people', 'The plan', 'The little details', 'The moments']).map((word, index) => <span key={`${word}-${index}`}>{word}<i>◆</i></span>)}</div>
        </section>

        <section className="moments-section section-space studio-moments" id="moments">
          <div className="section-intro"><div><p className="eyebrow">One workspace, from idea to event day</p><h2>Every moving part.<br /><span>One clear view.</span></h2></div><p>Bring the budget, timeline, vendors, and guest count together. See the plan as a whole, then work through one good next step.</p></div>
          <div className="feature-bento grid-flow-dense">
            <article className="bento-card bento-ripple">
              <div className="bento-ripple-art" aria-hidden="true"><div className="ripple-ring ring-outer" /><div className="ripple-ring ring-middle" /><div className="ripple-ring ring-inner" /><div className="ripple-point"><CircleDot size={21} /></div><div className="ripple-note note-budget"><small>Food & catering</small><strong>+ ₹50,000</strong></div><div className="ripple-note note-tables"><small>Tables to arrange</small><strong>15 <ArrowRight size={13} /> 20</strong></div></div>
              <div className="bento-card-copy"><span className="bento-kicker">Ripple Engine</span><h3>Know what a change<br />will touch.</h3><p>Preview the budget, seating, and follow-ups before anything is saved.</p><Link to="/events/moment-wedding-01/ripple" className="text-link">Explore the Ripple Engine <ArrowUpRight size={16} /></Link></div>
            </article>
            <article className="bento-card bento-budget">
              <div className="budget-mini-head"><span>WEDDING PLAN · ILLUSTRATIVE</span><span>₹6.0L</span></div>
              <div className="mini-budget-amount">₹5,80,000</div><p>Planned so far</p><div className="mini-budget-bar"><span /><span /><span /><span /><span /></div><div className="budget-mini-foot"><span>Still available</span><strong>₹20,000</strong></div>
              <div className="bento-card-copy"><span className="bento-kicker">Budget Studio</span><h3>Every rupee has a place.</h3><p>See estimates and actuals side by side, with assumptions clearly marked.</p></div><Link to="/events/moment-wedding-01/budget" className="card-link" aria-label="Explore Budget Studio"><ArrowUpRight size={18} /></Link>
            </article>
            <article className="bento-card bento-map">
              <div className="mini-timeline"><div className="mini-time-row done"><span className="mini-time-dot"><Check size={11} /></span><span><strong>Find your place</strong><small>Venue confirmed</small></span><small>Done</small></div><div className="mini-time-row active"><span className="mini-time-dot" /><span><strong>Shape the menu</strong><small>After your tasting</small></span><small>Next</small></div><div className="mini-time-row"><span className="mini-time-dot" /><span><strong>Send the invitations</strong><small>When your list is ready</small></span></div></div>
              <div className="bento-card-copy"><span className="bento-kicker">Moment Map</span><h3>Know what comes next.</h3><p>Milestones and dependencies keep the work in a helpful order.</p></div><Link to="/events/moment-wedding-01/map" className="card-link" aria-label="Explore Moment Map"><ArrowUpRight size={18} /></Link>
            </article>
          </div>
        </section>

        <section className="desire-section section-space studio-story" id="how-it-works">
          <div className="desire-heading"><p className="eyebrow">The reason for the plan</p><h2>Make room for<br /><span>the moment.</span></h2><p className="story-intro">A celebration changes as it gets closer. Your plan should keep up.</p></div>
          <div className="desire-layout"><div className="desire-image-wrap"><img className="reveal-image" src="/images/flowers-detail.webp" alt="A bouquet of fresh flowers in soft natural light" /><span className="image-caption">The details, quietly taken care of</span></div><div className="desire-copy-column"><p className="desire-copy"><span>Guests</span> <span>change.</span> <span>Budgets</span> <span>shift.</span> <span>Tasks</span> <span>depend</span> <span>on</span> <span>each</span> <span>other.</span> <span>MomentOS</span> <span>keeps</span> <span>the</span> <span>whole</span> <span>picture</span> <span>in</span> <span>view</span> <span>so</span> <span>you</span> <span>can</span> <span>be</span> <span>there</span> <span>for</span> <span>it.</span></p><div className="desire-footnote"><span className="footnote-dash" /><span>Good planning makes space for being present.</span></div></div></div>
        </section>

        <section className="event-types-section section-space studio-events" id="event-types">
          <div className="section-intro event-type-intro"><div><p className="eyebrow">Start with what brings you together</p><h2>Different days.<br /><span>Thoughtful plans.</span></h2></div><p>Choose an event to begin. Keep the details open until you are ready to decide.</p></div>
          <div className="event-accordion" aria-label="Explore event types">{gallery.map((item) => <Link key={item.type} to={`/events/new?type=${item.type}`} className={`event-accordion-item accordion-${item.type}`} style={{ backgroundImage: `linear-gradient(180deg, rgba(16,30,53,.02) 25%, rgba(16,30,53,.88) 100%), url(${item.src})` }}>
            <span className="accordion-vertical-title">{TYPE_COPY[item.type].label}</span><div className="accordion-copy"><span>{item.guests}</span><h3>{TYPE_COPY[item.type].label}</h3><p>{TYPE_COPY[item.type].description}</p><span className="accordion-action">Start this plan <ChevronRight size={15} /></span></div><span className="accordion-arrow"><ArrowUpRight size={19} /></span>
          </Link>)}</div>
        </section>

        <section className="principles-section section-space" aria-labelledby="principles-title">
          <div className="principles-intro"><p className="eyebrow">A steadier way to plan</p><h2 id="principles-title">Clarity, where<br />it counts.</h2><p>Helpful ideas with dependable guardrails. The plan stays yours from the first draft to the final decision.</p><div className="principle-controls"><button className="icon-button" aria-label="Show previous planning principle" onClick={() => movePrinciple(-1)}><ChevronLeft size={20} /></button><button className="icon-button" aria-label="Show next planning principle" onClick={() => movePrinciple(1)}><ChevronRight size={20} /></button></div></div>
          <div className="principle-stack" role="region" aria-roledescription="carousel" aria-label="MomentOS planning principles" aria-live="polite">{principles.map((principle, index) => {
            const depth = (index - activePrinciple + principles.length) % principles.length;
            return <article key={principle.label} className={`promise-card promise-${principle.tone}${depth === 0 ? ' is-active' : ''}`} style={{ '--stack-depth': depth, zIndex: principles.length - depth } as CSSProperties} aria-hidden={depth !== 0} aria-roledescription="slide">
              <div className="promise-card-face"><span className="bento-kicker">{principle.label}</span><h3>{principle.title}</h3><p>{principle.detail}</p></div>
            </article>;
          })}</div>
        </section>

        <section className="landing-cta-section studio-final-cta"><div className="cta-flower cta-flower-one" aria-hidden="true" /><div className="cta-flower cta-flower-two" aria-hidden="true" /><div className="landing-cta-inner"><p className="eyebrow">Your day, your way</p><h2>Make the plan.<br /><span>Be there for it.</span></h2><p>Tell us a little about what you’re planning. We’ll help you find a clear first step.</p><Link to="/events/new" className="button button-primary button-large">Start your plan <ArrowRight size={18} /></Link><span className="cta-small">No perfect brief required.</span></div></section>
      </main>
      <footer className="landing-footer studio-footer"><Brand /><span>Plan with clarity. Show up for the moment.</span><div><a href="#moments">The workspace</a><a href="#event-types">Your event</a><a href="#how-it-works">How it works</a>{import.meta.env.VITE_MOMENTOS_MODE === 'demo' ? <Link to="/events/moment-wedding-01">Explore the demo</Link> : null}</div><small>© 2026 MomentOS{import.meta.env.VITE_MOMENTOS_MODE === 'demo' ? ' · Offline demo' : ''}</small></footer>
    </div>
  );
}
