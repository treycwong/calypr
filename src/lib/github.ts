const GITHUB_API = "https://api.github.com";

function getGithubToken() {
  if (!process.env.GITHUB_TOKEN) {
    throw new Error("GITHUB_TOKEN is not set");
  }
  return process.env.GITHUB_TOKEN;
}

function headers() {
  return {
    Authorization: `Bearer ${getGithubToken()}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
  };
}

export async function addCollaborator(repo: string, username: string) {
  const owner = process.env.GITHUB_OWNER;
  const res = await fetch(
    `${GITHUB_API}/repos/${owner}/${repo}/collaborators/${username}`,
    {
      method: "PUT",
      headers: headers(),
    }
  );
  if (!res.ok && res.status !== 204) {
    const body = await res.text();
    throw new Error(`GitHub addCollaborator failed: ${res.status} ${body}`);
  }
  return true;
}

export async function removeCollaborator(repo: string, username: string) {
  const owner = process.env.GITHUB_OWNER;
  const res = await fetch(
    `${GITHUB_API}/repos/${owner}/${repo}/collaborators/${username}`,
    {
      method: "DELETE",
      headers: headers(),
    }
  );
  if (!res.ok && res.status !== 204) {
    const body = await res.text();
    throw new Error(`GitHub removeCollaborator failed: ${res.status} ${body}`);
  }
  return true;
}

export async function createIssue(
  repo: string,
  title: string,
  body: string,
  labels?: string[]
) {
  const owner = process.env.GITHUB_OWNER;
  const res = await fetch(`${GITHUB_API}/repos/${owner}/${repo}/issues`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ title, body, labels }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`GitHub createIssue failed: ${res.status} ${text}`);
  }
  const data = await res.json();
  return { number: data.number, url: data.html_url };
}
