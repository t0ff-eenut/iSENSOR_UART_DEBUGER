#include "mlp_float32.h"

/* 완전연결층: 행렬곱 + 편향 + 선택적 ReLU */
static void _fc(const float *in, int in_n, const float *W,
                const float *b, float *out, int out_n, int relu) {
    for (int i = 0; i < out_n; i++) {
        float s = b[i];
        for (int j = 0; j < in_n; j++) s += W[i * in_n + j] * in[j];
        out[i] = (relu && s < 0.0f) ? 0.0f : s;
    }
}

int mlp_float32_infer(const float *raw_input, float *human_prob) {
    /* Step 1: StandardScaler 정규화 */
    float x[25];
    for (int i = 0; i < 25; i++)
        x[i] = (raw_input[i] - MLP_SCALER_MEAN[i]) / MLP_SCALER_STD[i];

    /* Step 2: Layer 1 */
    float h1[128];
    _fc(x, 25, MLP_W1, MLP_B1, h1, 128, 1);

    /* Step 3: Layer 2 */
    float h2[64];
    _fc(h1, 128, MLP_W2, MLP_B2, h2, 64, 1);

    /* Step 4: Layer 3 */
    float h3[32];
    _fc(h2, 64, MLP_W3, MLP_B3, h3, 32, 1);

    /* Step 5: Layer 4 */
    float out[2];
    _fc(h3, 32, MLP_W4, MLP_B4, out, 2, 0);

    /* Step Final: Softmax → 확률 계산 */
    float mx = out[0] > out[1] ? out[0] : out[1];
    float e0 = expf(out[0] - mx), e1 = expf(out[1] - mx);
    *human_prob = e1 / (e0 + e1);
    return e1 > e0 ? 1 : 0;
}
