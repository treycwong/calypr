import type { Metadata } from "next";
import Link from "next/link";

import { LegalPage, type LegalSection } from "@/components/site/LegalPage";
import { LEGAL } from "@/lib/legal";
import { PLAN_LIMITS, PLANS } from "@/lib/plans";

export const metadata: Metadata = {
  title: "Terms of Service — Calypr",
  description: "The terms for using Calypr: accounts, plans and credits, refunds, your content, and acceptable use.",
};

// Every claim about what the product does here is meant to be true of the code as it stands
// (plans and limits come from `lib/plans`, the module /pricing reads). If billing, retention or
// refunds change, change this page in the same PR — the pricing FAQ follows the same rule.
const mail = <a href={`mailto:${LEGAL.contactEmail}`}>{LEGAL.contactEmail}</a>;

const SECTIONS: LegalSection[] = [
  {
    id: "agreement",
    title: "Who we are and this agreement",
    body: (
      <>
        <p>
          Calypr is operated by <strong>{LEGAL.operator}</strong>, based in{" "}
          {LEGAL.operatorLocation} (&ldquo;Calypr&rdquo;, &ldquo;we&rdquo;, &ldquo;us&rdquo;).
          These terms are an agreement between you and us for your use of calypr.co and
          everything on it: the canvas, the playground, share links, and the generated code.
        </p>
        <p>
          By creating an account or using Calypr you accept these terms and our{" "}
          <Link href="/privacy">Privacy Policy</Link>. If you use Calypr for an organisation, you
          accept them on its behalf and confirm you are allowed to.
        </p>
      </>
    ),
  },
  {
    id: "account",
    title: "Your account",
    body: (
      <ul>
        <li>
          You sign in with Google or GitHub. Keep that account secure: anything done through your
          Calypr account is your responsibility.
        </li>
        <li>You must be at least {LEGAL.minimumAge} years old to use Calypr.</li>
        <li>One person per account. Don&rsquo;t share it, and don&rsquo;t create extra accounts to get more free credits.</li>
        <li>
          You can delete your account at any time in Settings → Account. What happens to your
          data then is described in the <Link href="/privacy#retention">Privacy Policy</Link>.
        </li>
      </ul>
    ),
  },
  {
    id: "plans",
    title: "Plans, credits and billing",
    body: (
      <>
        <p>
          Calypr has a free plan and paid monthly plans, currently {PLANS.starter.name} at $
          {PLANS.starter.price} and {PLANS.plus.name} at ${PLANS.plus.price} a month. What each
          includes is listed on the <Link href="/pricing">pricing page</Link>, which forms part of
          these terms.
        </p>
        <ul>
          <li>
            <strong>Credits</strong>{" "}measure what our AI providers charge when your agents run on
            our keys. Each plan includes a monthly allowance (for example{" "}
            {PLAN_LIMITS.starter.credits} on {PLANS.starter.name}). Your balance is topped up to
            your allowance each month; unused credits don&rsquo;t roll over, and credits have no
            cash value.
          </li>
          <li>
            Runs on <strong>your own API key</strong>{" "}don&rsquo;t use credits; you pay that
            provider directly, under their terms.
          </li>
          <li>
            Paid plans renew automatically each month until cancelled. Payments are processed by
            Stripe; we never see or store your card details.
          </li>
          <li>
            Prices may include or exclude tax depending on where you are; Stripe shows the total
            before you pay.
          </li>
          <li>
            We may change prices or plan contents. We&rsquo;ll tell you by email at least 30 days
            before a price change affects your subscription, and you can cancel before it does.
          </li>
          <li>
            Credit costs per run follow our providers&rsquo; prices and may change with them. The
            pricing page shows typical costs.
          </li>
        </ul>
      </>
    ),
  },
  {
    id: "refunds",
    title: "Cancelling, downgrading and refunds",
    body: (
      <ul>
        <li>
          You can cancel or change plan at any time from Settings → Billing. Cancelling or
          downgrading takes effect at the end of the period you&rsquo;ve paid for; until then you
          keep your current plan.
        </li>
        <li>
          Upgrading takes effect immediately, and you&rsquo;re charged the prorated difference for
          the rest of the billing period.
        </li>
        <li>
          <strong>Refunds:</strong>{" "}if you ask within 7 days of a charge, we&rsquo;ll refund that
          charge in full and end the plan straight away. After 7 days, charges are not refunded,
          except where the law where you live says otherwise. Email {mail}.
        </li>
        <li>
          If your plan ends, anything over the new plan&rsquo;s limits becomes read-only rather
          than deleted, so you can still open and export it.
        </li>
      </ul>
    ),
  },
  {
    id: "content",
    title: "Your content",
    body: (
      <>
        <p>
          <strong>You own what you put into Calypr and what it produces for you</strong>: your
          projects and graphs, prompts, uploads, chat transcripts, generated images, audio, 3D
          models and video, and the Python code Calypr generates from your graphs.
        </p>
        <p>
          You give us permission to store, process and transmit that content only as needed to
          run Calypr for you: saving your projects, running your agents (including sending inputs
          to the AI providers your agents use), and showing results to anyone you share a link
          with. We don&rsquo;t use your content to train AI models, and we don&rsquo;t sell it.
        </p>
        <p>
          You are responsible for having the rights to what you upload, and for how you use what
          Calypr generates.
        </p>
      </>
    ),
  },
  {
    id: "ai",
    title: "AI output",
    body: (
      <p>
        Agents built in Calypr use AI models from third parties. Their output can be wrong,
        incomplete, biased or unexpected, and the same input can give different results. Check
        anything that matters before relying on it, and don&rsquo;t use Calypr as the only basis
        for medical, legal, financial or safety decisions. Templates are starting points, not
        professional advice.
      </p>
    ),
  },
  {
    id: "keys",
    title: "Your API keys, connectors and share links",
    body: (
      <ul>
        <li>
          If you add your own provider API key or connect an app (such as Notion or GitHub), you
          authorise us to use it on your behalf when your agents run. We store keys and tokens
          encrypted and use them for nothing else. You&rsquo;re responsible for that
          provider&rsquo;s terms and charges, and you can remove a key or disconnect an app at any
          time in Settings.
        </li>
        <li>
          A <strong>share link</strong>{" "}lets anyone who has it run that agent. Those runs use your
          credits and your keys, up to the run limit set on the link. You can revoke a link at any
          time; you&rsquo;re responsible for who you share it with.
        </li>
      </ul>
    ),
  },
  {
    id: "use",
    title: "Acceptable use",
    body: (
      <>
        <p>Don&rsquo;t use Calypr to:</p>
        <ul>
          <li>break the law, or help anyone else break it;</li>
          <li>
            create or spread content that sexualises minors, harasses or threatens people,
            promotes violence, or infringes someone else&rsquo;s rights;
          </li>
          <li>generate spam, malware, or deceptive content such as impersonation or fraud;</li>
          <li>
            get around credits, plan limits, rate limits or security measures, or resell access
            to Calypr or our provider keys;
          </li>
          <li>disrupt, probe or overload the service, or scrape it at scale;</li>
          <li>
            break the usage policies of the AI providers your agents use (for example
            OpenAI&rsquo;s), which apply to what you send through Calypr.
          </li>
        </ul>
        <p>
          We may remove content or suspend accounts that break these rules. Where we reasonably
          can, we&rsquo;ll tell you first and give you a chance to fix it.
        </p>
      </>
    ),
  },
  {
    id: "service",
    title: "Changes to the service",
    body: (
      <p>
        Calypr is under active development. We may add, change or remove features, models,
        templates and integrations. If we remove something that is a core part of a paid plan,
        we&rsquo;ll tell you in advance, and you can cancel and ask for a prorated refund of the
        time you&rsquo;ve paid for but can&rsquo;t use.
      </p>
    ),
  },
  {
    id: "ending",
    title: "Ending this agreement",
    body: (
      <p>
        You can stop using Calypr and delete your account at any time. We may suspend or close an
        account that seriously or repeatedly breaks these terms, or where the law requires it. If
        we close your account without a breach on your part, we&rsquo;ll refund any prepaid time
        you can no longer use.
      </p>
    ),
  },
  {
    id: "liability",
    title: "Warranties and liability",
    body: (
      <>
        <p>
          Calypr is provided &ldquo;as is&rdquo;. We work to keep it available and secure, but we
          don&rsquo;t promise it will be uninterrupted or error-free, or that AI output will be
          accurate.
        </p>
        <p>
          To the extent the law allows, we aren&rsquo;t liable for indirect or consequential
          losses, such as lost profits or data, and our total liability to you for any claim is
          limited to what you paid us in the 12 months before it. Nothing in these terms limits
          liability that can&rsquo;t be limited by law, or rights you have as a consumer that
          can&rsquo;t be waived.
        </p>
      </>
    ),
  },
  {
    id: "law",
    title: "Governing law",
    body: (
      <p>
        These terms are governed by the laws of {LEGAL.governingLaw}, and disputes will be heard
        by its courts, unless the law where you live gives you the right to bring a claim there.
      </p>
    ),
  },
  {
    id: "changes",
    title: "Changes to these terms",
    body: (
      <p>
        We&rsquo;ll update these terms as Calypr changes. For a material change we&rsquo;ll email
        you at least 30 days before it applies; continuing to use Calypr after that means you
        accept the new terms. The date at the top shows when they last changed.
      </p>
    ),
  },
  {
    id: "contact",
    title: "Contact",
    body: <p>Questions about these terms: {mail}.</p>,
  },
];

export default function TermsPage() {
  return (
    <LegalPage
      label="Legal"
      title="Terms of Service"
      intro={
        <p>
          The short version: you own what you build, plans renew monthly until you cancel, you
          can get a full refund within 7 days of a charge, and you shouldn&rsquo;t use Calypr for
          anything harmful. The details follow.
        </p>
      }
      sections={SECTIONS}
    />
  );
}
