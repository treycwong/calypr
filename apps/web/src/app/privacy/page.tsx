import type { Metadata } from "next";
import Link from "next/link";

import { LegalPage, type LegalSection } from "@/components/site/LegalPage";
import { LEGAL } from "@/lib/legal";

export const metadata: Metadata = {
  title: "Privacy Policy — Calypr",
  description: "What Calypr collects, why, who processes it, how long it's kept, and your choices.",
};

// Written from what the code does, not from a template: the providers below are the ones in the
// production configuration (2026-11-03), and the retention periods are the ones the API enforces
// (checkpoint TTL 7/30 days, `purge_grace_days` = 7). If a provider is added or a period changes,
// change this page in the same PR.
const mail = <a href={`mailto:${LEGAL.contactEmail}`}>{LEGAL.contactEmail}</a>;

const PROVIDERS: [string, string][] = [
  ["Vercel", "hosts the website and stores uploaded and generated files (United States)"],
  ["Railway", "runs the Calypr API that executes your agents (United States)"],
  ["Neon", "our database: accounts, projects, transcripts and usage (United States)"],
  ["Stripe", "takes payments and manages subscriptions"],
  ["Google and GitHub", "sign-in, when you choose to use them"],
  ["OpenAI", "text, image and voice models when your agents run on our keys"],
  ["fal", "3D and video generation when your agents run on our keys"],
  ["PostHog", "product analytics (United States)"],
];

const SECTIONS: LegalSection[] = [
  {
    id: "who",
    title: "Who we are",
    body: (
      <p>
        Calypr is operated by <strong>{LEGAL.operator}</strong>, based in{" "}
        {LEGAL.operatorLocation}. We decide how the personal data described here is used. For
        anything in this policy, email {mail}.
      </p>
    ),
  },
  {
    id: "collect",
    title: "What we collect",
    body: (
      <ul>
        <li>
          <strong>Account:</strong>{" "}your name, email address and profile picture from Google or
          GitHub when you sign in.
        </li>
        <li>
          <strong>Your work:</strong>{" "}projects and the graphs in them, prompts and settings, chat
          transcripts and run history, files you upload, and media your agents generate.
        </li>
        <li>
          <strong>Usage and billing:</strong>{" "}runs, the models used, token counts and credit costs,
          your plan, and your Stripe customer and subscription IDs. Card details go straight to
          Stripe; we never see or store them.
        </li>
        <li>
          <strong>Keys and connections:</strong>{" "}API keys you add and tokens for apps you connect
          (such as Notion or GitHub). These are stored encrypted.
        </li>
        <li>
          <strong>Analytics:</strong>{" "}pages visited and actions taken in the app (for example
          &ldquo;opened the code view&rdquo;), with browser, device and approximate location
          derived from your IP address.
        </li>
        <li>
          <strong>Messages:</strong>{" "}your email address if you join the updates list, and anything
          you send us by email.
        </li>
      </ul>
    ),
  },
  {
    id: "use",
    title: "How we use it",
    body: (
      <ul>
        <li>to run Calypr: sign you in, save your work, run your agents and show the results;</li>
        <li>to meter credits, take payments and enforce plan limits;</li>
        <li>to keep the service secure and prevent abuse;</li>
        <li>to understand how Calypr is used so we can improve it;</li>
        <li>to email you about your account, billing and important changes.</li>
      </ul>
    ),
  },
  {
    id: "ai",
    title: "AI providers and your content",
    body: (
      <>
        <p>
          When an agent runs, its inputs (your messages, prompts, uploaded images and the context
          it retrieves) are sent to the AI provider for that block, and the output comes back to
          Calypr. On our keys that means OpenAI for text, image and voice, and fal for 3D and
          video. If you add your own key for another provider, such as Anthropic or Moonshot,
          your inputs go to that provider under your own account with them.
        </p>
        <p>
          Tools and connected apps work the same way: a Notion or GitHub step reads from and
          writes to that service using the access you granted.
        </p>
        <p>
          <strong>We don&rsquo;t use your content to train AI models, and we don&rsquo;t sell it.</strong>{" "}
          Providers process it under their API terms, which for the providers we use exclude
          training on API data by default.
        </p>
      </>
    ),
  },
  {
    id: "sharing",
    title: "Who we share it with",
    body: (
      <>
        <p>We use these service providers, who process data only to provide their service to us:</p>
        <ul>
          {PROVIDERS.map(([name, what]) => (
            <li key={name}>
              <strong>{name}</strong>{" "}— {what}
            </li>
          ))}
        </ul>
        <p>
          <strong>Share links are public:</strong>{" "}anyone with a link you create can run that
          agent and see what it returns. Revoke a link to stop that.
        </p>
        <p>
          We may also disclose data if the law requires it, or to protect people from harm. If
          Calypr is sold or merged, your data would move to the new owner under this policy, and
          we&rsquo;d tell you first.
        </p>
      </>
    ),
  },
  {
    id: "retention",
    title: "How long we keep it",
    body: (
      <ul>
        <li>
          <strong>Agent memory</strong>{" "}(what an agent remembers mid-conversation) is kept for 7
          days on Free and 30 days on paid plans, then deleted.
        </li>
        <li>
          <strong>Projects, transcripts and files</strong>{" "}are kept until you delete them or your
          account.
        </li>
        <li>
          <strong>Deleting your account</strong>{" "}(Settings → Account) cancels any subscription
          and removes your access straight away. Your data is then permanently deleted after a
          7-day grace period, in case the deletion was a mistake.
        </li>
        <li>
          <strong>Billing records</strong>{" "}are kept for as long as tax and accounting law
          requires, even after you delete your account.
        </li>
        <li>
          <strong>Analytics</strong>{" "}are kept by PostHog under its standard retention.
        </li>
      </ul>
    ),
  },
  {
    id: "rights",
    title: "Your choices and rights",
    body: (
      <>
        <ul>
          <li>Delete projects, transcripts and files at any time, or your whole account.</li>
          <li>Remove an API key or disconnect an app in Settings.</li>
          <li>Ask us to take you off the updates list at any time.</li>
        </ul>
        <p>
          Depending on where you live, you may also have the right to access, correct, export or
          restrict the use of your personal data, or to object to it. Email {mail} and we&rsquo;ll
          respond within 30 days. You can also complain to your local data protection authority.
        </p>
      </>
    ),
  },
  {
    id: "cookies",
    title: "Cookies",
    body: (
      <p>
        We use cookies to keep you signed in and to remember small preferences, such as which
        workspace is open and whether the sidebar is collapsed. PostHog stores an identifier in
        your browser to count visits and actions. We don&rsquo;t use advertising cookies or sell
        data to advertisers.
      </p>
    ),
  },
  {
    id: "security",
    title: "Security",
    body: (
      <p>
        Data is sent over HTTPS. API keys and connector tokens are encrypted at rest, and
        each account&rsquo;s data is kept separate from every other&rsquo;s. No system is
        perfectly secure; if a breach affects your data, we&rsquo;ll tell you as the law
        requires.
      </p>
    ),
  },
  {
    id: "transfers",
    title: "Where your data is stored",
    body: (
      <p>
        Our servers and most of our providers are in the United States, so your data is
        processed there even if you live elsewhere. Where the law requires it, we rely on our
        providers&rsquo; standard safeguards for these transfers.
      </p>
    ),
  },
  {
    id: "children",
    title: "Children",
    body: (
      <p>
        Calypr isn&rsquo;t for anyone under {LEGAL.minimumAge}. If you believe a child has given
        us personal data, email {mail} and we&rsquo;ll delete it.
      </p>
    ),
  },
  {
    id: "changes",
    title: "Changes to this policy",
    body: (
      <p>
        We&rsquo;ll update this policy when what we collect or who processes it changes, and
        email you about significant changes. The date at the top shows when it last changed. See
        also our <Link href="/terms">Terms of Service</Link>.
      </p>
    ),
  },
];

export default function PrivacyPage() {
  return (
    <LegalPage
      label="Legal"
      title="Privacy Policy"
      intro={
        <p>
          The short version: we collect what we need to run Calypr, send your agents&rsquo;
          inputs to the AI providers that run them, never sell your data or train models on it,
          and delete it when you ask.
        </p>
      }
      sections={SECTIONS}
    />
  );
}
