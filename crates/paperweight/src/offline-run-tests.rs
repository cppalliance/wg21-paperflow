//! Runs the embedded prompt through the Harness with an offline broker, so a
//! runvil bump that breaks the prompt's parse, its role requirements, or its
//! Lua fails here instead of on the first real run against a Gateway.

use std::num::NonZeroU32;
use std::sync::{Arc, Mutex};

use harness::pack::{HostContext, HostServices, PackRegistry};
use harness::record::{MemoryRecorder, RunErrorKind, RunOutcome};
use harness::vfs::VfsRef;
use harness::{BoxFuture, Harness, HostSnapshot, InferenceBroker, RunReport, RunRequest, Timer};
use runvil::effect::Round;
use runvil::error::Error;
use runvil::model::{
    Completion, CompletionOptions, CompletionResult, Message, ModelBinding, ModelCatalog, ModelId,
    ModelInfo, Temperature, ThinkingMode, ToolSchema,
};

use super::{DEFAULT_PROMPT, DEFAULT_PROMPT_FILE, DEFAULT_PROMPT_NAME, TokioTimer};

/// A small paper with two H2 sections, enough for the prompt to split.
const PAPER: &str = "# P9999R0: An offline paper\n\n## Motivation\n\n\
                     Users need this facility.\n\n## Design\n\nIt works like this.\n";

/// Every reply the broker gives: a proposal (no `NOT_PROPOSAL`) that a Grade
/// arm reads as a 0 with no quote, and that Analyze takes as its prose.
const REPLY: &str = "SCORE: 0\nQUOTE:";

/// The request settings one round was sent with.
#[derive(Debug, Clone, Copy, PartialEq)]
struct Sent {
    thinking: Option<bool>,
    temperature: Option<f64>,
}

/// Lists one model and answers every round with [`REPLY`], keeping the
/// settings each round was sent with.
#[derive(Debug)]
struct Offline {
    model: ModelInfo,
    sent: Arc<Mutex<Vec<Sent>>>,
}

impl InferenceBroker for Offline {
    fn models(&self) -> BoxFuture<Result<ModelCatalog, Error>> {
        let catalog = ModelCatalog::new([self.model.clone()]);
        Box::pin(async move { catalog })
    }

    fn chat(
        &self,
        _binding: ModelBinding,
        _messages: Vec<Message>,
        _tools: Vec<ToolSchema>,
        options: CompletionOptions,
        _round: Round,
    ) -> BoxFuture<Result<Box<Completion>, Error>> {
        let sent = Sent {
            thinking: options.thinking(),
            temperature: options.temperature().map(Temperature::get),
        };
        self.sent
            .lock()
            .unwrap_or_else(|e| panic!("lock: {e}"))
            .push(sent);
        let reply = Completion::from_result(CompletionResult::Text(REPLY.to_owned()), "offline");
        Box::pin(async move { reply.map(Box::new) })
    }
}

/// Runs the embedded prompt on one offline model with `context` tokens and
/// `thinking` mode, returning the report and the settings of every round.
async fn run_offline(context: u32, thinking: ThinkingMode) -> (RunReport, Vec<Sent>) {
    let id = ModelId::gateway("offline").unwrap_or_else(|e| panic!("model id: {e}"));
    let context = NonZeroU32::new(context).unwrap_or_else(|| panic!("zero context"));
    let sent = Arc::new(Mutex::new(Vec::new()));
    let broker = Offline {
        model: ModelInfo::new(id, "offline test model", context, thinking),
        sent: Arc::clone(&sent),
    };
    let timer: Arc<dyn Timer> = Arc::new(TokioTimer);
    let harness = Harness::new(
        Arc::new(MemoryRecorder::new()),
        Arc::new(broker),
        timer,
        Arc::new(HostContext::new(PackRegistry::new(), HostServices::new())),
        HostServices::new(),
    );
    let report = harness
        .run(RunRequest {
            name: DEFAULT_PROMPT_NAME.to_owned(),
            source: DEFAULT_PROMPT.to_owned(),
            file: DEFAULT_PROMPT_FILE.to_owned(),
            args: String::new(),
            input_text: Some(PAPER.to_owned()),
            vfs: VfsRef::default(),
            host: HostSnapshot::default(),
        })
        .await
        .unwrap_or_else(|e| panic!("record the run: {e}"));
    let sent = sent.lock().unwrap_or_else(|e| panic!("lock: {e}")).clone();
    (report, sent)
}

/// Returns the kind and message of a failed run, panicking on any other
/// outcome.
fn failure(report: &RunReport) -> (RunErrorKind, &str) {
    match &report.outcome {
        RunOutcome::Failed { kind, message } => (*kind, message.as_str()),
        other => panic!("expected a failed run, got {other:?}"),
    }
}

#[tokio::test]
async fn embedded_prompt_runs_to_its_report_offline() {
    let (report, sent) = run_offline(65536, ThinkingMode::Switchable).await;

    assert!(
        matches!(report.outcome, RunOutcome::Completed { .. }),
        "the run must complete, got {:?}",
        report.outcome
    );
    let output = report
        .output
        .unwrap_or_else(|e| panic!("the run must leave report.md: {e}"));
    assert!(output.starts_with("Weight: "), "report: {output:?}");
    assert!(
        sent.len() > 2,
        "triage, the Grade arms, and Analyze must each ask the model, got {} rounds",
        sent.len()
    );
    for round in &sent {
        assert_eq!(
            *round,
            Sent {
                thinking: Some(false),
                temperature: Some(0.3),
            },
            "every round runs on `default` with thinking off at temperature 0.3",
        );
    }
}

#[tokio::test]
async fn embedded_prompt_refuses_a_model_below_its_context_minimum() {
    let (report, sent) = run_offline(16000, ThinkingMode::Switchable).await;

    let (kind, message) = failure(&report);
    assert_eq!(kind, RunErrorKind::RequirementsUnmet, "message: {message}");
    assert!(
        message.contains("role 'default': requires a context of at least 32768 tokens"),
        "message: {message}"
    );
    assert!(sent.is_empty(), "a refused run asks no model");
}

#[tokio::test]
async fn embedded_prompt_refuses_an_always_thinking_model() {
    let (report, sent) = run_offline(65536, ThinkingMode::Always).await;

    let (kind, message) = failure(&report);
    assert_eq!(kind, RunErrorKind::RequirementsUnmet, "message: {message}");
    assert!(
        message.contains("role 'default': requires 'thinking: false'"),
        "message: {message}"
    );
    assert!(sent.is_empty(), "a refused run asks no model");
}
