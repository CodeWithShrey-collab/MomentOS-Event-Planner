import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowDown, ArrowRight, ArrowUpRight, CalendarHeart, Check, ChevronRight, CircleDot } from 'lucide-react';
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

export function LandingPage() {
  const [ownedEvents, setOwnedEvents] = useState<{id:string;title:string}[]>([]);
  useEffect(() => { let active=true; demoApi.listEvents().then(r=>{if(active)setOwnedEvents(r.data);}).catch(()=>{if(active)setOwnedEvents([]);}); return ()=>{active=false;}; }, []);
  const pageRef = useRef<HTMLDivElement>(null);
  useGSAP(() => {
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduceMotion) return;
    gsap.utils.toArray<HTMLElement>('.reveal-image').forEach((image) => {
      gsap.fromTo(image, { scale: 0.94, opacity: 0.6 }, {
        scale: 1, opacity: 1, ease: 'none',
        scrollTrigger: { trigger: image, start: 'top 86%', end: 'bottom 15%', scrub: true },
      });
    });
    gsap.fromTo('.desire-copy span', { opacity: 0.2 }, {
      opacity: 1, stagger: 0.08, ease: 'none',
      scrollTrigger: { trigger: '.desire-copy', start: 'top 72%', end: 'bottom 40%', scrub: true },
    });
  }, { scope: pageRef });

  return (
    <div className="landing" ref={pageRef}>
      <div className="landing-nav-wrap"><header className="landing-nav"><Brand /><nav aria-label="Main navigation"><a href="#moments">The workspace</a><a href="#how-it-works">How it works</a></nav><div className="landing-nav-actions">{import.meta.env.VITE_MOMENTOS_MODE === 'demo' ? <Link to="/events/moment-wedding-01" className="nav-signin">Explore demo</Link> : ownedEvents[0] ? <Link to={`/events/${ownedEvents[0].id}`} className="nav-signin">My events</Link> : null}<Link to="/events/new" className="button button-primary button-small">Start planning <ArrowRight size={15} /></Link></div></header></div>

      <main className="landing-main">
        <section className="hero-section" aria-labelledby="hero-title">
          <div className="hero-copy">
            <p className="eyebrow hero-eyebrow"><span className="eyebrow-line" /> The celebration starts here</p>
            <h1 id="hero-title">Every little detail,<br /><em>held with care.</em></h1>
            <p className="hero-description">Turn the celebration in your head into a plan you can actually move through. Budget, people, timing — all in one thoughtful place.</p>
            <div className="hero-actions"><Link to="/events/new" className="button button-primary button-large">Start planning <ArrowRight size={18} /></Link><a href="#how-it-works" className="button button-secondary button-large">See how it works <ArrowDown size={16} /></a></div>
            <div className="hero-note"><span className="note-avatars"><i>M</i><i>A</i><i>R</i></span><span>A little more clarity for the people bringing it all together.</span></div>
          </div>
          <div className="hero-art" aria-label="An intimate garden celebration at golden hour">
            <img className="hero-image reveal-image" src="/images/celebration-hero.webp" alt="A couple celebrating their wedding with a bouquet at golden hour" />
            <div className="hero-image-wash" />
            <div className="hero-art-label"><span>12 December · Nagpur</span><strong>A day made of little moments</strong></div>
            <div className="hero-paper-note"><span className="paper-note-icon"><CalendarHeart size={16} /></span><span><strong>Thoughtfully planned</strong><small>Every detail, in its place</small></span><Check size={15} className="paper-check" /></div>
            <span className="hero-ornament hero-ornament-one" /><span className="hero-ornament hero-ornament-two" />
          </div>
          <a className="scroll-cue" href="#moments"><span className="scroll-cue-line" /> A plan with room for life <ArrowDown size={14} /></a>
        </section>

        <section className="marquee-section" aria-label="What MomentOS brings together">
          <div className="marquee-track" aria-hidden="true">{['The people', 'The plan', 'The little details', 'The moments'].concat(['The people', 'The plan', 'The little details', 'The moments']).map((word, index) => <span key={`${word}-${index}`}>{word}<i>·</i></span>)}</div>
        </section>

        <section className="moments-section section-space" id="moments">
          <div className="section-intro"><div><p className="eyebrow">A calmer way to celebrate</p><h2>One good plan<br />makes room for <em>more.</em></h2></div><p>From the first idea to the last little check, keep the moving pieces close — and the reason you’re doing it in view.</p></div>
        <div className="feature-bento grid-flow-dense">
            <article className="bento-card bento-ripple">
              <div className="bento-ripple-art"><div className="ripple-ring ring-outer" /><div className="ripple-ring ring-middle" /><div className="ripple-ring ring-inner" /><div className="ripple-point"><CircleDot size={21} /></div><div className="ripple-note note-budget"><small>Food & catering</small><strong>+ ₹50,000</strong></div><div className="ripple-note note-tables"><small>Tables to arrange</small><strong>15 <ArrowRight size={13} /> 20</strong></div></div>
              <div className="bento-card-copy"><span className="bento-kicker">See the ripple</span><h3>Know what a change<br />will touch.</h3><p>Try a new guest count and see the budget, seating and follow-ups move together — before anything is saved.</p><Link to="/events/moment-wedding-01/ripple" className="text-link">Explore the Ripple Engine <ArrowUpRight size={16} /></Link></div>
            </article>
            <article className="bento-card bento-budget"><div className="budget-mini-head"><span>Plan at a glance</span><span>₹ 6.0L</span></div><div className="mini-budget-amount">₹ 5,80,000</div><p>Planned so far</p><div className="mini-budget-bar"><span /><span /><span /><span /><span /></div><div className="budget-mini-foot"><span>Within your plan</span><strong>₹ 20,000 left</strong></div><div className="bento-card-copy"><span className="bento-kicker">Keep perspective</span><h3>Your budget, with<br />the whole picture.</h3><p>See where it’s going, what’s still an estimate and where you have room.</p></div><Link to="/events/moment-wedding-01/budget" className="card-link" aria-label="Explore Budget Studio"><ArrowUpRight size={18} /></Link></article>
            <article className="bento-card bento-map"><div className="mini-timeline"><div className="mini-time-row done"><span className="mini-time-dot"><Check size={11} /></span><span><strong>Find your place</strong><small>Venue confirmed</small></span><small>Done</small></div><div className="mini-time-row active"><span className="mini-time-dot" /><span><strong>Shape the menu</strong><small>After your tasting</small></span><small>Next</small></div><div className="mini-time-row"><span className="mini-time-dot" /><span><strong>Send the invitations</strong><small>When your list is ready</small></span></div></div><div className="bento-card-copy"><span className="bento-kicker">Know what comes next</span><h3>Every task finds<br />its moment.</h3><p>Milestones and dependencies help the work feel lighter and more in order.</p></div><Link to="/events/moment-wedding-01/map" className="card-link" aria-label="Explore Moment Map"><ArrowUpRight size={18} /></Link></article>
          </div>
        </section>

        <section className="desire-section section-space" id="how-it-works">
          <div className="desire-heading"><p className="eyebrow">The day is the point</p><h2>Make room for <em>the moment.</em></h2></div>
          <div className="desire-layout"><div className="desire-image-wrap"><img className="reveal-image" src="/images/flowers-detail.webp" alt="A bouquet of fresh flowers in soft natural light" /><span className="image-caption">The details, quietly taken care of</span></div><div className="desire-copy-column"><p className="desire-copy"><span>Plans</span> <span>change.</span> <span>Guests</span> <span>grow.</span> <span>And</span> <span>the</span> <span>best</span> <span>moments</span> <span>never</span> <span>follow</span> <span>a</span> <span>script.</span> <span>MomentOS</span> <span>helps</span> <span>you</span> <span>hold</span> <span>the</span> <span>whole</span> <span>picture</span> <span>so</span> <span>you</span> <span>can</span> <span>be</span> <span>there</span> <span>for</span> <span>it.</span></p><div className="desire-footnote"><span className="footnote-dash" /><span>Good planning makes space for being present.</span></div></div></div>
        </section>

        <section className="event-types-section section-space">
          <div className="section-intro event-type-intro"><div><p className="eyebrow">Whatever brings you together</p><h2>Made for your kind<br />of <em>moment.</em></h2></div><p>Start with what you know. Keep the rest open until you are ready to decide.</p></div>
          <div className="event-accordion">{gallery.map((item, index) => <Link key={item.type} to={`/events/new?type=${item.type}`} className={`event-accordion-item accordion-${item.type}`} style={{ backgroundImage: `linear-gradient(180deg, transparent 20%, rgba(31, 27, 29, .78) 100%), url(${item.src})` }}>
            <span className="accordion-number">0{index + 1}</span><div className="accordion-copy"><span>{item.guests}</span><h3>{TYPE_COPY[item.type].label}</h3><p>{TYPE_COPY[item.type].description}</p><span className="accordion-action">Start this plan <ChevronRight size={15} /></span></div><span className="accordion-arrow"><ArrowUpRight size={19} /></span>
          </Link>)}</div>
          <div className="inline-image-thought"><p>“The most important detail is <span className="inline-image-chip" role="img" aria-label="A shared table at a celebration" style={{ backgroundImage: `url(${gallery[0]!.src})` }} /> the people who make it feel like yours.”</p><span>Made for every reason to gather.</span></div>
        </section>

        <section className="landing-cta-section"><div className="cta-flower cta-flower-one" /><div className="cta-flower cta-flower-two" /><div className="landing-cta-inner"><p className="eyebrow">Your day, your way</p><h2>Begin with the<br /><em>feeling.</em></h2><p>Tell us a little about what you’re planning. We’ll help you find a clear first step.</p><Link to="/events/new" className="button button-light button-large">Start your plan <ArrowRight size={18} /></Link><span className="cta-small">No perfect brief required.</span></div></section>
      </main>
      <footer className="landing-footer"><Brand /><span>Made for the moments that matter.</span><div><a href="#moments">The workspace</a><a href="#how-it-works">How it works</a>{import.meta.env.VITE_MOMENTOS_MODE === 'demo' ? <Link to="/events/moment-wedding-01">Explore the demo</Link> : null}</div><small>© 2026 MomentOS{import.meta.env.VITE_MOMENTOS_MODE === 'demo' ? ' · Offline demo' : ''}</small></footer>
    </div>
  );
}
